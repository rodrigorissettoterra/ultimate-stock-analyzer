from __future__ import annotations

import gzip
from collections import Counter, defaultdict
from datetime import date, datetime
from pathlib import Path
from statistics import mean
from typing import Literal

from pydantic import BaseModel, Field

from ultimate_stock_analyzer.backtesting.historical_model_routes import (
    HistoricalModelRouteRegistry,
)
from ultimate_stock_analyzer.bootstrap.dataset import BootstrapDataset
from ultimate_stock_analyzer.collectors.bcb_ifdata import bank_contract_values
from ultimate_stock_analyzer.domain.master import (
    BankPrudentialAnnualRecord,
    FinancialStatementLine,
    IssuerRecord,
    SectorClassificationRecord,
    SecurityRecord,
)
from ultimate_stock_analyzer.fundamentals.contracts import (
    BANK_PRUDENTIAL_CONTRACT,
    GENERAL_CORPORATE_CONTRACT,
    evaluate_contract,
)
from ultimate_stock_analyzer.fundamentals.cvm_accounts import (
    GENERAL_CORPORATE_FIXED_ACCOUNTS,
    AccountExtraction,
    extract_fixed_accounts,
)
from ultimate_stock_analyzer.scoring.sector_models import SectorModelRegistry

HISTORICAL_MODEL_ROUTE_UNSUPPORTED_MODEL = "HISTORICAL_MODEL_ROUTE_UNSUPPORTED_MODEL"
HISTORICAL_MODEL_ROUTE_REGISTRY_UNAVAILABLE = "HISTORICAL_MODEL_ROUTE_REGISTRY_UNAVAILABLE"

CoverageApplicability = Literal[
    "GENERAL_CORPORATE_APPLICABLE",
    "BANK_ACCOUNTING_CONTRACT_AVAILABLE",
    "SPECIALIZED_ACCOUNTING_CONTRACT_REQUIRED",
    "UNRESOLVED_SECTOR_CLASSIFICATION",
    "UNRESOLVED_SECTOR_MODEL",
]
SummaryApplicability = Literal[
    "CURRENT_SECTOR_MODEL_RESOLVED",
    "PARTIAL_SECTOR_MODEL_RESOLUTION",
    "HISTORICAL_SECTOR_MODEL_RESOLVED",
    "PARTIAL_HISTORICAL_SECTOR_MODEL_RESOLUTION",
    "UNRESOLVED_SECTOR_CLASSIFICATION",
]
SectorRoutingSource = Literal[
    "CURRENT_B3",
    "HISTORICAL_MODEL_ROUTE",
    "UNRESOLVED",
]
SPECIALIZED_ACCOUNTING_MODELS = frozenset({"banks", "insurance"})
GENERAL_ACCOUNTING_MODELS = frozenset({"general_corporate", "utilities", "commodities"})


class FundamentalCoverageRecord(BaseModel):
    company_id: str
    cvm_code: int
    company_name: str
    tickers: list[str]
    reference_date: date
    fiscal_year: int
    contract: str = GENERAL_CORPORATE_CONTRACT.name
    applicability: CoverageApplicability = "UNRESOLVED_SECTOR_CLASSIFICATION"
    sector: str | None = None
    subsector: str | None = None
    segment: str | None = None
    listing_segment: str | None = None
    sector_model_id: str | None = None
    sector_model_reason: str | None = None
    sector_model_is_fallback: bool | None = None
    sector_classification_point_in_time_eligible: bool | None = None
    sector_routing_source: SectorRoutingSource = "UNRESOLVED"
    historical_as_of: datetime | None = None
    historical_model_route_admissible: bool | None = None
    historical_model_route_blockers: list[str] = Field(default_factory=list)
    historical_model_route_model_id: str | None = None
    historical_model_route_available_from: datetime | None = None
    historical_model_route_evidence_source: str | None = None
    historical_model_route_source_document: str | None = None
    extracted_accounts: int = Field(ge=0)
    critical_coverage: float = Field(ge=0.0, le=1.0)
    total_coverage: float = Field(ge=0.0, le=1.0)
    point_in_time_critical_coverage: float = Field(ge=0.0, le=1.0)
    missing_critical: list[str]
    missing_supporting: list[str]
    untimed_critical: list[str]
    not_yet_available_critical: list[str] = Field(default_factory=list)
    source_documents: list[str]
    latest_available_from: datetime | None = None
    has_prior_fiscal_year: bool = False
    longitudinal_pair_ready: bool = False


class FundamentalCoverageSummary(BaseModel):
    schema_version: str = "1.3"
    bootstrap_run_id: str
    bootstrap_manifest_sha256: str
    generated_at: datetime
    contract: str = GENERAL_CORPORATE_CONTRACT.name
    applicability: SummaryApplicability = "UNRESOLVED_SECTOR_CLASSIFICATION"
    historical_as_of: datetime | None = None
    companies: int = Field(ge=0)
    company_years: int = Field(ge=0)
    mapped_tickers: int = Field(ge=0)
    critical_complete_company_years: int = Field(ge=0)
    point_in_time_critical_complete_company_years: int = Field(ge=0)
    longitudinal_pair_ready_company_years: int = Field(ge=0)
    resolved_sector_model_company_years: int = Field(ge=0)
    historical_route_company_years: int = Field(default=0, ge=0)
    historical_route_admissible_company_years: int = Field(default=0, ge=0)
    historical_route_gap_company_years: int = Field(default=0, ge=0)
    bank_contract_available_company_years: int = Field(ge=0)
    specialized_contract_required_company_years: int = Field(ge=0)
    general_corporate_applicable_company_years: int = Field(ge=0)
    mean_critical_coverage: float = Field(ge=0.0, le=1.0)
    mean_total_coverage: float = Field(ge=0.0, le=1.0)
    coverage_buckets: dict[str, int]
    sector_model_counts: dict[str, int]
    warnings: list[str]


class FundamentalCoverageProfiler:
    """Measure evidence readiness without producing an investment score."""

    def __init__(
        self,
        dataset: BootstrapDataset,
        *,
        sector_registry: SectorModelRegistry | None = None,
    ) -> None:
        self.dataset = dataset
        self.sector_registry = sector_registry

    def analyze(
        self,
        *,
        generated_at: datetime,
        as_of: datetime | None = None,
    ) -> tuple[list[FundamentalCoverageRecord], FundamentalCoverageSummary]:
        _validate_as_of(as_of)
        issuers = {issuer.company_id: issuer for issuer in self.dataset.issuers()}
        securities = self.dataset.securities()
        statements = self.dataset.statements()
        classifications = {
            item.company_id: item for item in self.dataset.sector_classifications()
        }
        bank_profiles = {
            (item.company_id, item.fiscal_year): item
            for item in self.dataset.bank_profiles()
        }
        historical_routes = (
            HistoricalModelRouteRegistry(self.dataset.historical_model_routes())
            if as_of is not None
            else None
        )

        by_period: dict[tuple[str, date], list[FinancialStatementLine]] = defaultdict(list)
        for line in statements:
            if line.fiscal_order != "ÚLTIMO":
                continue
            if as_of is not None and line.reference_date > as_of.date():
                continue
            by_period[(line.company_id, line.reference_date)].append(line)

        records: list[FundamentalCoverageRecord] = []
        for (company_id, reference_date), lines in sorted(by_period.items()):
            issuer = issuers.get(company_id)
            if issuer is None:
                issuer = _issuer_from_line(lines[0])

            if as_of is None:
                sector_context = self._sector_context(classifications.get(company_id))
            else:
                assert historical_routes is not None
                sector_context = self._historical_sector_context(
                    routes=historical_routes,
                    company_id=company_id,
                    fiscal_year=reference_date.year,
                    as_of=as_of,
                )

            bank_profile = bank_profiles.get((company_id, reference_date.year))
            if sector_context["sector_model_id"] == "banks" and bank_profile is not None:
                record = _bank_coverage_record(
                    issuer=issuer,
                    securities=securities,
                    reference_date=reference_date,
                    sector_context=sector_context,
                    profile=bank_profile,
                    as_of=as_of,
                )
            else:
                force_pit_zero = bool(
                    as_of is not None
                    and (
                        not sector_context["historical_model_route_admissible"]
                        or sector_context["applicability"]
                        == "SPECIALIZED_ACCOUNTING_CONTRACT_REQUIRED"
                    )
                )
                record = _general_coverage_record(
                    issuer=issuer,
                    securities=securities,
                    reference_date=reference_date,
                    lines=lines,
                    sector_context=sector_context,
                    as_of=as_of,
                    force_point_in_time_zero=force_pit_zero,
                )
            records.append(record)

        _mark_longitudinal_pairs(records)
        summary = _summary(
            records,
            self.dataset,
            generated_at,
            historical_as_of=as_of,
        )
        return records, summary

    def _sector_context(
        self,
        classification: SectorClassificationRecord | None,
    ) -> dict[str, object]:
        if classification is None:
            return _unresolved_sector_context(
                applicability="UNRESOLVED_SECTOR_CLASSIFICATION",
            )
        base: dict[str, object] = {
            "sector": classification.sector,
            "subsector": classification.subsector,
            "segment": classification.segment,
            "listing_segment": classification.listing_segment,
            "point_in_time_eligible": classification.point_in_time_eligible,
            "sector_routing_source": "CURRENT_B3",
            "historical_as_of": None,
            "historical_model_route_admissible": None,
            "historical_model_route_blockers": [],
            "historical_model_route_model_id": None,
            "historical_model_route_available_from": None,
            "historical_model_route_evidence_source": None,
            "historical_model_route_source_document": None,
        }
        if self.sector_registry is None:
            return {
                **base,
                "applicability": "UNRESOLVED_SECTOR_MODEL",
                "sector_model_id": None,
                "sector_model_reason": None,
                "sector_model_is_fallback": None,
            }
        selection = self.sector_registry.select(
            {
                "sector": classification.sector,
                "subsector": classification.subsector,
                "segment": classification.segment,
            }
        )
        applicability: CoverageApplicability = (
            "SPECIALIZED_ACCOUNTING_CONTRACT_REQUIRED"
            if selection.model_id in SPECIALIZED_ACCOUNTING_MODELS
            else "GENERAL_CORPORATE_APPLICABLE"
        )
        return {
            **base,
            "applicability": applicability,
            "sector_model_id": selection.model_id,
            "sector_model_reason": selection.reason,
            "sector_model_is_fallback": selection.is_fallback,
        }

    def _historical_sector_context(
        self,
        *,
        routes: HistoricalModelRouteRegistry,
        company_id: str,
        fiscal_year: int,
        as_of: datetime,
    ) -> dict[str, object]:
        decision = routes.decision(
            company_id=company_id,
            fiscal_year=fiscal_year,
            as_of=as_of,
            require_point_in_time=True,
        )
        route = decision.route
        blockers = list(decision.blockers)
        route_model_id = route.model_id if route is not None else None

        if decision.admissible:
            if self.sector_registry is None:
                blockers.append(HISTORICAL_MODEL_ROUTE_REGISTRY_UNAVAILABLE)
            elif not _registry_contains_model(self.sector_registry, route_model_id):
                blockers.append(HISTORICAL_MODEL_ROUTE_UNSUPPORTED_MODEL)
            elif route_model_id not in (
                GENERAL_ACCOUNTING_MODELS | SPECIALIZED_ACCOUNTING_MODELS
            ):
                blockers.append(HISTORICAL_MODEL_ROUTE_UNSUPPORTED_MODEL)

        admissible = decision.admissible and not blockers
        if not admissible:
            context = _unresolved_sector_context(
                applicability="UNRESOLVED_SECTOR_MODEL",
            )
            return {
                **context,
                "sector_routing_source": "HISTORICAL_MODEL_ROUTE",
                "historical_as_of": as_of,
                "historical_model_route_admissible": False,
                "historical_model_route_blockers": blockers,
                "historical_model_route_model_id": route_model_id,
                "historical_model_route_available_from": (
                    route.available_from if route is not None else None
                ),
                "historical_model_route_evidence_source": (
                    route.evidence_source if route is not None else None
                ),
                "historical_model_route_source_document": (
                    route.source_document if route is not None else None
                ),
            }

        assert route is not None
        applicability: CoverageApplicability = (
            "SPECIALIZED_ACCOUNTING_CONTRACT_REQUIRED"
            if route.model_id in SPECIALIZED_ACCOUNTING_MODELS
            else "GENERAL_CORPORATE_APPLICABLE"
        )
        return {
            "applicability": applicability,
            "sector": None,
            "subsector": None,
            "segment": None,
            "listing_segment": None,
            "sector_model_id": route.model_id,
            "sector_model_reason": route.reason or "historical_model_route",
            "sector_model_is_fallback": False,
            "point_in_time_eligible": None,
            "sector_routing_source": "HISTORICAL_MODEL_ROUTE",
            "historical_as_of": as_of,
            "historical_model_route_admissible": True,
            "historical_model_route_blockers": [],
            "historical_model_route_model_id": route.model_id,
            "historical_model_route_available_from": route.available_from,
            "historical_model_route_evidence_source": route.evidence_source,
            "historical_model_route_source_document": route.source_document,
        }

    def write(
        self,
        output_root: str | Path,
        *,
        generated_at: datetime,
        as_of: datetime | None = None,
    ) -> FundamentalCoverageSummary:
        records, summary = self.analyze(generated_at=generated_at, as_of=as_of)
        output_dir = Path(output_root) / "coverage" / self.dataset.manifest.run_id
        if output_dir.exists():
            raise FileExistsError(f"coverage output already exists: {output_dir}")
        output_dir.mkdir(parents=True)
        with gzip.open(
            output_dir / "fundamental_coverage.jsonl.gz",
            "wt",
            encoding="utf-8",
            newline="\n",
        ) as file:
            for record in records:
                file.write(record.model_dump_json())
                file.write("\n")
        (output_dir / "summary.json").write_text(
            summary.model_dump_json(indent=2),
            encoding="utf-8",
            newline="\n",
        )
        return summary


def _bank_coverage_record(
    *,
    issuer: IssuerRecord,
    securities: list[SecurityRecord],
    reference_date: date,
    sector_context: dict[str, object],
    profile: BankPrudentialAnnualRecord,
    as_of: datetime | None,
) -> FundamentalCoverageRecord:
    values = bank_contract_values(profile)
    coverage = evaluate_contract(values, BANK_PRUDENTIAL_CONTRACT)
    critical_names = set(BANK_PRUDENTIAL_CONTRACT.critical_inputs)

    if as_of is None:
        point_in_time_coverage = (
            coverage.critical_coverage if profile.point_in_time_eligible else 0.0
        )
        untimed_critical = (
            []
            if profile.point_in_time_eligible
            else sorted(name for name in critical_names if name in values)
        )
        not_yet_available_critical: list[str] = []
    else:
        timestamp = profile.available_from_estimate
        timestamp_visible = _timestamp_visible(timestamp, as_of)
        eligible_and_visible = profile.point_in_time_eligible and timestamp_visible
        point_in_time_coverage = (
            coverage.critical_coverage if eligible_and_visible else 0.0
        )
        present_critical = sorted(name for name in critical_names if name in values)
        if not profile.point_in_time_eligible or not _timestamp_usable(timestamp):
            untimed_critical = present_critical
            not_yet_available_critical = []
        elif timestamp is not None and timestamp > as_of:
            untimed_critical = []
            not_yet_available_critical = present_critical
        else:
            untimed_critical = []
            not_yet_available_critical = []

    return FundamentalCoverageRecord(
        company_id=issuer.company_id,
        cvm_code=issuer.cvm_code,
        company_name=issuer.legal_name,
        tickers=_tickers_for_period(securities, issuer.company_id, reference_date),
        reference_date=reference_date,
        fiscal_year=reference_date.year,
        contract=BANK_PRUDENTIAL_CONTRACT.name,
        applicability="BANK_ACCOUNTING_CONTRACT_AVAILABLE",
        sector=sector_context["sector"],
        subsector=sector_context["subsector"],
        segment=sector_context["segment"],
        listing_segment=sector_context["listing_segment"],
        sector_model_id=sector_context["sector_model_id"],
        sector_model_reason=sector_context["sector_model_reason"],
        sector_model_is_fallback=sector_context["sector_model_is_fallback"],
        sector_classification_point_in_time_eligible=sector_context[
            "point_in_time_eligible"
        ],
        sector_routing_source=sector_context["sector_routing_source"],
        historical_as_of=sector_context["historical_as_of"],
        historical_model_route_admissible=sector_context[
            "historical_model_route_admissible"
        ],
        historical_model_route_blockers=sector_context[
            "historical_model_route_blockers"
        ],
        historical_model_route_model_id=sector_context[
            "historical_model_route_model_id"
        ],
        historical_model_route_available_from=sector_context[
            "historical_model_route_available_from"
        ],
        historical_model_route_evidence_source=sector_context[
            "historical_model_route_evidence_source"
        ],
        historical_model_route_source_document=sector_context[
            "historical_model_route_source_document"
        ],
        extracted_accounts=len(values),
        critical_coverage=coverage.critical_coverage,
        total_coverage=coverage.total_coverage,
        point_in_time_critical_coverage=point_in_time_coverage,
        missing_critical=list(coverage.missing_critical),
        missing_supporting=list(coverage.missing_supporting),
        untimed_critical=untimed_critical,
        not_yet_available_critical=not_yet_available_critical,
        source_documents=list(profile.source_documents),
        latest_available_from=profile.available_from_estimate,
    )


def _general_coverage_record(
    *,
    issuer: IssuerRecord,
    securities: list[SecurityRecord],
    reference_date: date,
    lines: list[FinancialStatementLine],
    sector_context: dict[str, object],
    as_of: datetime | None,
    force_point_in_time_zero: bool,
) -> FundamentalCoverageRecord:
    extraction = extract_fixed_accounts(
        lines,
        company_id=issuer.company_id,
        reference_date=reference_date,
        consolidation_scope=None,
    )
    coverage = evaluate_contract(extraction.values)
    critical_names = set(GENERAL_CORPORATE_CONTRACT.critical_inputs)

    if as_of is None:
        untimed_critical = sorted(
            name
            for name in critical_names
            if name in extraction.lines
            and not _timestamp_usable(extraction.lines[name].available_from)
        )
        timed_critical = sum(
            1
            for name in critical_names
            if name in extraction.lines
            and _timestamp_usable(extraction.lines[name].available_from)
        )
        point_in_time_coverage = (
            timed_critical / len(critical_names) if critical_names else 1.0
        )
        visible_extraction = extraction
        not_yet_available_critical: list[str] = []
    else:
        visible_lines = [
            line for line in lines if _timestamp_visible(line.available_from, as_of)
        ]
        visible_extraction = extract_fixed_accounts(
            visible_lines,
            company_id=issuer.company_id,
            reference_date=reference_date,
            consolidation_scope=None,
        )
        visible_coverage = evaluate_contract(visible_extraction.values)
        point_in_time_coverage = (
            0.0
            if force_point_in_time_zero
            else visible_coverage.critical_coverage
        )
        untimed_critical, not_yet_available_critical = _critical_visibility_gaps(
            lines=lines,
            reference_date=reference_date,
            company_id=issuer.company_id,
            full_extraction=extraction,
            visible_extraction=visible_extraction,
            as_of=as_of,
            critical_names=critical_names,
        )

    available_times = [
        line.available_from
        for line in visible_extraction.lines.values()
        if _timestamp_usable(line.available_from)
    ]
    source_documents = sorted(
        {
            line.source_document
            for line in visible_extraction.lines.values()
            if line.source_document
        }
    )
    return FundamentalCoverageRecord(
        company_id=issuer.company_id,
        cvm_code=issuer.cvm_code,
        company_name=issuer.legal_name,
        tickers=_tickers_for_period(securities, issuer.company_id, reference_date),
        reference_date=reference_date,
        fiscal_year=reference_date.year,
        applicability=sector_context["applicability"],
        sector=sector_context["sector"],
        subsector=sector_context["subsector"],
        segment=sector_context["segment"],
        listing_segment=sector_context["listing_segment"],
        sector_model_id=sector_context["sector_model_id"],
        sector_model_reason=sector_context["sector_model_reason"],
        sector_model_is_fallback=sector_context["sector_model_is_fallback"],
        sector_classification_point_in_time_eligible=sector_context[
            "point_in_time_eligible"
        ],
        sector_routing_source=sector_context["sector_routing_source"],
        historical_as_of=sector_context["historical_as_of"],
        historical_model_route_admissible=sector_context[
            "historical_model_route_admissible"
        ],
        historical_model_route_blockers=sector_context[
            "historical_model_route_blockers"
        ],
        historical_model_route_model_id=sector_context[
            "historical_model_route_model_id"
        ],
        historical_model_route_available_from=sector_context[
            "historical_model_route_available_from"
        ],
        historical_model_route_evidence_source=sector_context[
            "historical_model_route_evidence_source"
        ],
        historical_model_route_source_document=sector_context[
            "historical_model_route_source_document"
        ],
        extracted_accounts=len(extraction.values),
        critical_coverage=coverage.critical_coverage,
        total_coverage=coverage.total_coverage,
        point_in_time_critical_coverage=point_in_time_coverage,
        missing_critical=list(coverage.missing_critical),
        missing_supporting=list(coverage.missing_supporting),
        untimed_critical=untimed_critical,
        not_yet_available_critical=not_yet_available_critical,
        source_documents=source_documents,
        latest_available_from=max(available_times) if available_times else None,
    )


def _critical_visibility_gaps(
    *,
    lines: list[FinancialStatementLine],
    reference_date: date,
    company_id: str,
    full_extraction: AccountExtraction,
    visible_extraction: AccountExtraction,
    as_of: datetime,
    critical_names: set[str],
) -> tuple[list[str], list[str]]:
    untimed: list[str] = []
    not_yet: list[str] = []
    definitions = {
        account.name: account
        for account in GENERAL_CORPORATE_FIXED_ACCOUNTS
        if account.name in critical_names
    }

    for name in sorted(critical_names):
        if name in visible_extraction.values or name not in full_extraction.values:
            continue
        definition = definitions.get(name)
        if definition is None:
            continue
        candidates = [
            line
            for line in lines
            if line.company_id == company_id
            and line.reference_date == reference_date
            and line.fiscal_order == "ÚLTIMO"
            and line.statement in definition.statements
            and line.account_code == definition.code
        ]
        usable_times = [
            line.available_from
            for line in candidates
            if _timestamp_usable(line.available_from)
        ]
        if any(timestamp > as_of for timestamp in usable_times):
            not_yet.append(name)
        else:
            untimed.append(name)

    return untimed, not_yet


def _unresolved_sector_context(
    *,
    applicability: CoverageApplicability,
) -> dict[str, object]:
    return {
        "applicability": applicability,
        "sector": None,
        "subsector": None,
        "segment": None,
        "listing_segment": None,
        "sector_model_id": None,
        "sector_model_reason": None,
        "sector_model_is_fallback": None,
        "point_in_time_eligible": None,
        "sector_routing_source": "UNRESOLVED",
        "historical_as_of": None,
        "historical_model_route_admissible": None,
        "historical_model_route_blockers": [],
        "historical_model_route_model_id": None,
        "historical_model_route_available_from": None,
        "historical_model_route_evidence_source": None,
        "historical_model_route_source_document": None,
    }


def _registry_contains_model(
    registry: SectorModelRegistry,
    model_id: str | None,
) -> bool:
    if model_id is None:
        return False
    return model_id == registry.default_model.model_id or any(
        model.model_id == model_id for model in registry.models
    )


def _validate_as_of(as_of: datetime | None) -> None:
    if as_of is not None and (as_of.tzinfo is None or as_of.utcoffset() is None):
        raise ValueError("fundamental coverage historical as_of must be timezone-aware")


def _timestamp_usable(value: datetime | None) -> bool:
    return value is not None and value.tzinfo is not None and value.utcoffset() is not None


def _timestamp_visible(value: datetime | None, as_of: datetime) -> bool:
    if not _timestamp_usable(value):
        return False
    assert value is not None
    return value <= as_of


def _issuer_from_line(line: FinancialStatementLine) -> IssuerRecord:
    return IssuerRecord(
        company_id=line.company_id,
        cvm_code=line.cvm_code,
        cnpj=line.cnpj,
        legal_name=line.company_name,
        collected_at=line.collected_at,
        source=line.source,
    )


def _tickers_for_period(
    securities: list[SecurityRecord],
    company_id: str,
    reference_date: date,
) -> list[str]:
    candidates = [
        security
        for security in securities
        if security.company_id == company_id
        and (security.trading_start is None or security.trading_start <= reference_date)
        and (security.trading_end is None or security.trading_end >= reference_date)
    ]
    if not candidates:
        candidates = [security for security in securities if security.company_id == company_id]
    return sorted({security.ticker.upper() for security in candidates})


def _mark_longitudinal_pairs(records: list[FundamentalCoverageRecord]) -> None:
    by_company_year = {(record.company_id, record.fiscal_year): record for record in records}
    for record in records:
        prior = by_company_year.get((record.company_id, record.fiscal_year - 1))
        record.has_prior_fiscal_year = prior is not None
        record.longitudinal_pair_ready = (
            prior is not None
            and record.point_in_time_critical_coverage == 1.0
            and prior.point_in_time_critical_coverage == 1.0
        )


def _summary(
    records: list[FundamentalCoverageRecord],
    dataset: BootstrapDataset,
    generated_at: datetime,
    *,
    historical_as_of: datetime | None,
) -> FundamentalCoverageSummary:
    critical_complete = sum(record.critical_coverage == 1.0 for record in records)
    point_in_time_complete = sum(
        record.point_in_time_critical_coverage == 1.0 for record in records
    )
    longitudinal = sum(record.longitudinal_pair_ready for record in records)
    resolved = sum(record.sector_model_id is not None for record in records)
    historical_route_records = [
        record
        for record in records
        if record.historical_model_route_admissible is not None
    ]
    historical_admissible = sum(
        record.historical_model_route_admissible is True
        for record in historical_route_records
    )
    bank_available = sum(
        record.applicability == "BANK_ACCOUNTING_CONTRACT_AVAILABLE"
        for record in records
    )
    specialized = sum(
        record.applicability == "SPECIALIZED_ACCOUNTING_CONTRACT_REQUIRED"
        for record in records
    )
    general = sum(
        record.applicability == "GENERAL_CORPORATE_APPLICABLE" for record in records
    )

    if historical_as_of is not None:
        if records and historical_admissible == len(records):
            applicability: SummaryApplicability = "HISTORICAL_SECTOR_MODEL_RESOLVED"
        elif historical_admissible:
            applicability = "PARTIAL_HISTORICAL_SECTOR_MODEL_RESOLUTION"
        else:
            applicability = "UNRESOLVED_SECTOR_CLASSIFICATION"
    elif not records or resolved == 0:
        applicability = "UNRESOLVED_SECTOR_CLASSIFICATION"
    elif resolved == len(records):
        applicability = "CURRENT_SECTOR_MODEL_RESOLVED"
    else:
        applicability = "PARTIAL_SECTOR_MODEL_RESOLUTION"

    buckets = {
        "critical_100pct": critical_complete,
        "critical_90_to_99pct": sum(
            0.9 <= record.critical_coverage < 1.0 for record in records
        ),
        "critical_75_to_89pct": sum(
            0.75 <= record.critical_coverage < 0.9 for record in records
        ),
        "critical_below_75pct": sum(
            record.critical_coverage < 0.75 for record in records
        ),
    }
    model_counts = Counter(
        record.sector_model_id for record in records if record.sector_model_id is not None
    )

    warnings = [
        "General corporates use the CVM general-corporate accounting contract.",
        "Banks with normalized IFData evidence use bank_prudential_ifdata_v1; insurers still require a specialized accounting contract.",
        "IFData annual bank profiles are latest-state historical rows and are not point-in-time eligible until revision history is captured.",
        "B3 sector classification is a current collection-time snapshot and is not point-in-time eligible for historical walk-forward/backtests.",
        "Coverage readiness and sector routing are not investment scores or recommendations.",
    ]
    if historical_as_of is not None:
        warnings.append(
            "Historical coverage routing uses persisted HistoricalModelRoute evidence only; current B3 classification is diagnostic and never a fallback."
        )
        warnings.append(
            "Historical fundamental coverage uses only statement revisions whose available_from timestamp is visible at the requested as_of."
        )

    return FundamentalCoverageSummary(
        bootstrap_run_id=dataset.manifest.run_id,
        bootstrap_manifest_sha256=dataset.manifest_sha256,
        generated_at=generated_at,
        applicability=applicability,
        historical_as_of=historical_as_of,
        companies=len({record.company_id for record in records}),
        company_years=len(records),
        mapped_tickers=len({ticker for record in records for ticker in record.tickers}),
        critical_complete_company_years=critical_complete,
        point_in_time_critical_complete_company_years=point_in_time_complete,
        longitudinal_pair_ready_company_years=longitudinal,
        resolved_sector_model_company_years=resolved,
        historical_route_company_years=len(historical_route_records),
        historical_route_admissible_company_years=historical_admissible,
        historical_route_gap_company_years=(
            len(historical_route_records) - historical_admissible
        ),
        bank_contract_available_company_years=bank_available,
        specialized_contract_required_company_years=specialized,
        general_corporate_applicable_company_years=general,
        mean_critical_coverage=(
            mean(record.critical_coverage for record in records) if records else 0.0
        ),
        mean_total_coverage=(
            mean(record.total_coverage for record in records) if records else 0.0
        ),
        coverage_buckets=buckets,
        sector_model_counts=dict(sorted(model_counts.items())),
        warnings=warnings,
    )
