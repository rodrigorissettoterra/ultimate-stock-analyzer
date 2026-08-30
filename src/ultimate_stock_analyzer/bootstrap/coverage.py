from __future__ import annotations

import gzip
from collections import Counter, defaultdict
from datetime import date, datetime
from pathlib import Path
from statistics import mean
from typing import Literal

from pydantic import BaseModel, Field

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
from ultimate_stock_analyzer.fundamentals.cvm_accounts import extract_fixed_accounts
from ultimate_stock_analyzer.scoring.sector_models import SectorModelRegistry

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
    "UNRESOLVED_SECTOR_CLASSIFICATION",
]
SPECIALIZED_ACCOUNTING_MODELS = frozenset({"banks", "insurance"})


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
    extracted_accounts: int = Field(ge=0)
    critical_coverage: float = Field(ge=0.0, le=1.0)
    total_coverage: float = Field(ge=0.0, le=1.0)
    point_in_time_critical_coverage: float = Field(ge=0.0, le=1.0)
    missing_critical: list[str]
    missing_supporting: list[str]
    untimed_critical: list[str]
    source_documents: list[str]
    latest_available_from: datetime | None = None
    has_prior_fiscal_year: bool = False
    longitudinal_pair_ready: bool = False


class FundamentalCoverageSummary(BaseModel):
    schema_version: str = "1.2"
    bootstrap_run_id: str
    bootstrap_manifest_sha256: str
    generated_at: datetime
    contract: str = GENERAL_CORPORATE_CONTRACT.name
    applicability: SummaryApplicability = "UNRESOLVED_SECTOR_CLASSIFICATION"
    companies: int = Field(ge=0)
    company_years: int = Field(ge=0)
    mapped_tickers: int = Field(ge=0)
    critical_complete_company_years: int = Field(ge=0)
    point_in_time_critical_complete_company_years: int = Field(ge=0)
    longitudinal_pair_ready_company_years: int = Field(ge=0)
    resolved_sector_model_company_years: int = Field(ge=0)
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
    ) -> tuple[list[FundamentalCoverageRecord], FundamentalCoverageSummary]:
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

        by_period: dict[tuple[str, date], list[FinancialStatementLine]] = defaultdict(list)
        for line in statements:
            if line.fiscal_order != "ÚLTIMO":
                continue
            by_period[(line.company_id, line.reference_date)].append(line)

        records: list[FundamentalCoverageRecord] = []
        for (company_id, reference_date), lines in sorted(by_period.items()):
            issuer = issuers.get(company_id)
            if issuer is None:
                issuer = _issuer_from_line(lines[0])
            sector_context = self._sector_context(classifications.get(company_id))
            bank_profile = bank_profiles.get((company_id, reference_date.year))
            if sector_context["sector_model_id"] == "banks" and bank_profile is not None:
                record = _bank_coverage_record(
                    issuer=issuer,
                    securities=securities,
                    reference_date=reference_date,
                    sector_context=sector_context,
                    profile=bank_profile,
                )
            else:
                record = _general_coverage_record(
                    issuer=issuer,
                    securities=securities,
                    reference_date=reference_date,
                    lines=lines,
                    sector_context=sector_context,
                )
            records.append(record)

        _mark_longitudinal_pairs(records)
        summary = _summary(records, self.dataset, generated_at)
        return records, summary

    def _sector_context(
        self,
        classification: SectorClassificationRecord | None,
    ) -> dict[str, object]:
        if classification is None:
            return {
                "applicability": "UNRESOLVED_SECTOR_CLASSIFICATION",
                "sector": None,
                "subsector": None,
                "segment": None,
                "listing_segment": None,
                "sector_model_id": None,
                "sector_model_reason": None,
                "sector_model_is_fallback": None,
                "point_in_time_eligible": None,
            }
        base: dict[str, object] = {
            "sector": classification.sector,
            "subsector": classification.subsector,
            "segment": classification.segment,
            "listing_segment": classification.listing_segment,
            "point_in_time_eligible": classification.point_in_time_eligible,
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

    def write(
        self,
        output_root: str | Path,
        *,
        generated_at: datetime,
    ) -> FundamentalCoverageSummary:
        records, summary = self.analyze(generated_at=generated_at)
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
) -> FundamentalCoverageRecord:
    values = bank_contract_values(profile)
    coverage = evaluate_contract(values, BANK_PRUDENTIAL_CONTRACT)
    critical_names = set(BANK_PRUDENTIAL_CONTRACT.critical_inputs)
    point_in_time_coverage = (
        coverage.critical_coverage if profile.point_in_time_eligible else 0.0
    )
    untimed_critical = (
        []
        if profile.point_in_time_eligible
        else sorted(name for name in critical_names if name in values)
    )
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
        extracted_accounts=len(values),
        critical_coverage=coverage.critical_coverage,
        total_coverage=coverage.total_coverage,
        point_in_time_critical_coverage=point_in_time_coverage,
        missing_critical=list(coverage.missing_critical),
        missing_supporting=list(coverage.missing_supporting),
        untimed_critical=untimed_critical,
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
) -> FundamentalCoverageRecord:
    extraction = extract_fixed_accounts(
        lines,
        company_id=issuer.company_id,
        reference_date=reference_date,
        consolidation_scope=None,
    )
    coverage = evaluate_contract(extraction.values)
    critical_names = set(GENERAL_CORPORATE_CONTRACT.critical_inputs)
    untimed_critical = sorted(
        name
        for name in critical_names
        if name in extraction.lines
        and extraction.lines[name].available_from is None
    )
    timed_critical = sum(
        1
        for name in critical_names
        if name in extraction.lines
        and extraction.lines[name].available_from is not None
    )
    point_in_time_coverage = (
        timed_critical / len(critical_names) if critical_names else 1.0
    )
    available_times = [
        line.available_from
        for line in extraction.lines.values()
        if line.available_from is not None
    ]
    source_documents = sorted(
        {
            line.source_document
            for line in extraction.lines.values()
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
        extracted_accounts=len(extraction.values),
        critical_coverage=coverage.critical_coverage,
        total_coverage=coverage.total_coverage,
        point_in_time_critical_coverage=point_in_time_coverage,
        missing_critical=list(coverage.missing_critical),
        missing_supporting=list(coverage.missing_supporting),
        untimed_critical=untimed_critical,
        source_documents=source_documents,
        latest_available_from=max(available_times) if available_times else None,
    )


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
) -> FundamentalCoverageSummary:
    critical_complete = sum(record.critical_coverage == 1.0 for record in records)
    point_in_time_complete = sum(
        record.point_in_time_critical_coverage == 1.0 for record in records
    )
    longitudinal = sum(record.longitudinal_pair_ready for record in records)
    resolved = sum(record.sector_model_id is not None for record in records)
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
    if not records or resolved == 0:
        applicability: SummaryApplicability = "UNRESOLVED_SECTOR_CLASSIFICATION"
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
        "critical_below_75pct": sum(record.critical_coverage < 0.75 for record in records),
    }
    model_counts = Counter(
        record.sector_model_id for record in records if record.sector_model_id is not None
    )
    return FundamentalCoverageSummary(
        bootstrap_run_id=dataset.manifest.run_id,
        bootstrap_manifest_sha256=dataset.manifest_sha256,
        generated_at=generated_at,
        applicability=applicability,
        companies=len({record.company_id for record in records}),
        company_years=len(records),
        mapped_tickers=len({ticker for record in records for ticker in record.tickers}),
        critical_complete_company_years=critical_complete,
        point_in_time_critical_complete_company_years=point_in_time_complete,
        longitudinal_pair_ready_company_years=longitudinal,
        resolved_sector_model_company_years=resolved,
        bank_contract_available_company_years=bank_available,
        specialized_contract_required_company_years=specialized,
        general_corporate_applicable_company_years=general,
        mean_critical_coverage=mean(record.critical_coverage for record in records) if records else 0.0,
        mean_total_coverage=mean(record.total_coverage for record in records) if records else 0.0,
        coverage_buckets=buckets,
        sector_model_counts=dict(sorted(model_counts.items())),
        warnings=[
            "General corporates use the CVM general-corporate accounting contract.",
            "Banks with normalized IFData evidence use bank_prudential_ifdata_v1; insurers still require a specialized accounting contract.",
            "IFData annual bank profiles are latest-state historical rows and are not point-in-time eligible until revision history is captured.",
            "B3 sector classification is a current collection-time snapshot and is not point-in-time eligible for historical walk-forward/backtests.",
            "Coverage readiness and sector routing are not investment scores or recommendations.",
        ],
    )
