from __future__ import annotations

import gzip
import json
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, Field

from ultimate_stock_analyzer.backtesting.historical_model_routes import (
    HISTORICAL_MODEL_ROUTE_MISSING,
)
from ultimate_stock_analyzer.bootstrap.coverage import (
    FundamentalCoverageRecord,
    FundamentalCoverageSummary,
)
from ultimate_stock_analyzer.bootstrap.dataset import BootstrapDataset

SECTOR_ROUTING_NOT_POINT_IN_TIME = "SECTOR_ROUTING_NOT_POINT_IN_TIME"
SECTOR_ROUTING_UNAVAILABLE = "SECTOR_ROUTING_UNAVAILABLE"
BANK_EVIDENCE_NOT_POINT_IN_TIME = "BANK_EVIDENCE_NOT_POINT_IN_TIME"
FUNDAMENTAL_POINT_IN_TIME_COVERAGE_INCOMPLETE = (
    "FUNDAMENTAL_POINT_IN_TIME_COVERAGE_INCOMPLETE"
)
SPECIALIZED_ACCOUNTING_CONTRACT_MISSING = "SPECIALIZED_ACCOUNTING_CONTRACT_MISSING"
SECURITY_HISTORY_INCOMPLETE = "SECURITY_HISTORY_INCOMPLETE"
PRICE_HISTORY_INCOMPLETE = "PRICE_HISTORY_INCOMPLETE"
PRICE_SERIES_UNADJUSTED_FOR_CORPORATE_ACTIONS = (
    "PRICE_SERIES_UNADJUSTED_FOR_CORPORATE_ACTIONS"
)
NO_FUNDAMENTAL_COMPANY_YEARS = "NO_FUNDAMENTAL_COMPANY_YEARS"

CRITICAL_INPUTS_MISSING = "CRITICAL_INPUTS_MISSING"
CRITICAL_INPUTS_NOT_POINT_IN_TIME = "CRITICAL_INPUTS_NOT_POINT_IN_TIME"
CRITICAL_INPUTS_NOT_YET_AVAILABLE = "CRITICAL_INPUTS_NOT_YET_AVAILABLE"
SPECIALIZED_EVIDENCE_NOT_POINT_IN_TIME = "SPECIALIZED_EVIDENCE_NOT_POINT_IN_TIME"
UNATTRIBUTED_POINT_IN_TIME_GAP = "UNATTRIBUTED_POINT_IN_TIME_GAP"


class FundamentalPointInTimeGap(BaseModel):
    company_id: str
    fiscal_year: int
    tickers: list[str]
    contract: str
    applicability: str
    sector_model_id: str | None = None
    point_in_time_critical_coverage: float = Field(ge=0.0, le=1.0)
    missing_critical: list[str]
    untimed_critical: list[str]
    not_yet_available_critical: list[str] = Field(default_factory=list)
    historical_model_route_blockers: list[str] = Field(default_factory=list)
    latest_available_from: datetime | None = None
    causes: list[str]


class HistoricalModelRouteGap(BaseModel):
    company_id: str
    fiscal_year: int
    tickers: list[str]
    model_id: str | None = None
    available_from: datetime | None = None
    evidence_source: str | None = None
    source_document: str | None = None
    blockers: list[str]


class HistoricalBacktestReadinessReport(BaseModel):
    schema_version: str = "1.2"
    effect: str = "diagnostic_only_no_scoring_or_weight_promotion"
    generated_at: datetime
    bootstrap_run_id: str
    bootstrap_manifest_sha256: str
    start_year: int
    end_year: int
    requested_tickers: list[str]
    source_policy: str
    historical_as_of: datetime | None = None

    fundamental_companies: int = Field(ge=0)
    fundamental_company_years: int = Field(ge=0)
    point_in_time_critical_complete_company_years: int = Field(ge=0)
    fundamental_point_in_time_gap_count: int = Field(ge=0)
    fundamental_point_in_time_gap_details_complete: bool
    fundamental_point_in_time_gaps: list[FundamentalPointInTimeGap]
    longitudinal_pair_ready_company_years: int = Field(ge=0)
    resolved_sector_model_company_years: int = Field(ge=0)
    specialized_contract_required_company_years: int = Field(ge=0)

    historical_route_company_years: int = Field(default=0, ge=0)
    historical_route_admissible_company_years: int = Field(default=0, ge=0)
    historical_route_gap_count: int = Field(default=0, ge=0)
    historical_route_gap_details_complete: bool = False
    historical_model_route_gaps: list[HistoricalModelRouteGap] = Field(default_factory=list)
    current_b3_fallback_used: bool = False

    sector_classification_records: int = Field(ge=0)
    point_in_time_sector_classification_records: int = Field(ge=0)
    bank_profiles: int = Field(ge=0)
    point_in_time_bank_profiles: int = Field(ge=0)

    expected_ticker_years: int = Field(ge=0)
    security_ticker_years: int = Field(ge=0)
    price_ticker_years: int = Field(ge=0)
    missing_security_ticker_years: list[str]
    missing_price_ticker_years: list[str]
    price_bars: int = Field(ge=0)
    adjusted_price_bars: int = Field(ge=0)
    unadjusted_price_bars: int = Field(ge=0)

    blockers: list[str]
    strict_historical_backtest_data_ready: bool
    walk_forward_data_ready: bool
    weight_promotion_evaluated: bool = False
    point_in_time_eligible: bool


def audit_historical_backtest_readiness(
    dataset: BootstrapDataset,
    coverage: FundamentalCoverageSummary,
    *,
    generated_at: datetime,
    coverage_records: list[FundamentalCoverageRecord] | None = None,
    as_of: datetime | None = None,
) -> HistoricalBacktestReadinessReport:
    """Audit whether one bootstrap run can safely feed M15/M16 historical evaluation.

    With no ``as_of`` the legacy current-state diagnostic remains unchanged. When
    ``as_of`` is supplied, sector routing is evaluated exclusively from persisted
    historical-model-route decisions carried by the coverage records. Current B3
    classification remains diagnostic and is never promoted as a historical fallback.
    """

    _validate_historical_mode(
        coverage=coverage,
        coverage_records=coverage_records,
        as_of=as_of,
    )

    manifest = dataset.manifest
    years = tuple(range(manifest.start_year, manifest.end_year + 1))
    requested = tuple(ticker.upper() for ticker in manifest.requested_tickers)
    expected_ticker_years = {(year, ticker) for year in years for ticker in requested}

    security_ticker_years = _ticker_years(
        dataset,
        artifact_name="cvm_security_master",
    )
    price_rows = _price_rows(dataset)
    price_ticker_years = {(year, ticker) for year, ticker, _adjusted in price_rows}
    adjusted_price_bars = sum(adjusted for _year, _ticker, adjusted in price_rows)
    price_bars = len(price_rows)
    unadjusted_price_bars = price_bars - adjusted_price_bars

    classifications = dataset.sector_classifications()
    bank_profiles = dataset.bank_profiles()
    point_in_time_classifications = sum(
        item.point_in_time_eligible for item in classifications
    )
    point_in_time_bank_profiles = sum(item.point_in_time_eligible for item in bank_profiles)

    missing_security = sorted(expected_ticker_years - security_ticker_years)
    missing_prices = sorted(expected_ticker_years - price_ticker_years)

    fundamental_gap_count = max(
        coverage.company_years - coverage.point_in_time_critical_complete_company_years,
        0,
    )
    fundamental_gaps = _fundamental_pit_gaps(coverage_records or [])
    gap_details_complete = coverage_records is not None
    if gap_details_complete and len(fundamental_gaps) != fundamental_gap_count:
        raise ValueError(
            "fundamental PIT gap detail count does not match coverage summary: "
            f"summary={fundamental_gap_count} details={len(fundamental_gaps)}"
        )

    route_gaps = _historical_route_gaps(coverage_records or []) if as_of is not None else []
    historical_route_company_years = (
        coverage.historical_route_company_years if as_of is not None else 0
    )
    historical_route_admissible = (
        coverage.historical_route_admissible_company_years if as_of is not None else 0
    )
    historical_route_gap_count = (
        coverage.historical_route_gap_company_years if as_of is not None else 0
    )
    if as_of is not None and len(route_gaps) != historical_route_gap_count:
        raise ValueError(
            "historical route gap detail count does not match coverage summary: "
            f"summary={historical_route_gap_count} details={len(route_gaps)}"
        )

    blockers: set[str] = set()
    if coverage.company_years == 0:
        blockers.add(NO_FUNDAMENTAL_COMPANY_YEARS)
    if fundamental_gap_count:
        blockers.add(FUNDAMENTAL_POINT_IN_TIME_COVERAGE_INCOMPLETE)
    if coverage.specialized_contract_required_company_years:
        blockers.add(SPECIALIZED_ACCOUNTING_CONTRACT_MISSING)

    if as_of is None:
        if not classifications:
            blockers.add(SECTOR_ROUTING_UNAVAILABLE)
        elif point_in_time_classifications != len(classifications):
            blockers.add(SECTOR_ROUTING_NOT_POINT_IN_TIME)
    else:
        for gap in route_gaps:
            blockers.update(gap.blockers)

    if bank_profiles and point_in_time_bank_profiles != len(bank_profiles):
        blockers.add(BANK_EVIDENCE_NOT_POINT_IN_TIME)

    if requested and missing_security:
        blockers.add(SECURITY_HISTORY_INCOMPLETE)
    if requested and missing_prices:
        blockers.add(PRICE_HISTORY_INCOMPLETE)
    if unadjusted_price_bars:
        blockers.add(PRICE_SERIES_UNADJUSTED_FOR_CORPORATE_ACTIONS)

    ordered_blockers = sorted(blockers)
    ready = not ordered_blockers
    return HistoricalBacktestReadinessReport(
        generated_at=generated_at,
        bootstrap_run_id=manifest.run_id,
        bootstrap_manifest_sha256=dataset.manifest_sha256,
        start_year=manifest.start_year,
        end_year=manifest.end_year,
        requested_tickers=list(requested),
        source_policy=manifest.source_policy,
        historical_as_of=as_of,
        fundamental_companies=coverage.companies,
        fundamental_company_years=coverage.company_years,
        point_in_time_critical_complete_company_years=(
            coverage.point_in_time_critical_complete_company_years
        ),
        fundamental_point_in_time_gap_count=fundamental_gap_count,
        fundamental_point_in_time_gap_details_complete=gap_details_complete,
        fundamental_point_in_time_gaps=fundamental_gaps,
        longitudinal_pair_ready_company_years=(
            coverage.longitudinal_pair_ready_company_years
        ),
        resolved_sector_model_company_years=(
            coverage.resolved_sector_model_company_years
        ),
        specialized_contract_required_company_years=(
            coverage.specialized_contract_required_company_years
        ),
        historical_route_company_years=historical_route_company_years,
        historical_route_admissible_company_years=historical_route_admissible,
        historical_route_gap_count=historical_route_gap_count,
        historical_route_gap_details_complete=as_of is not None,
        historical_model_route_gaps=route_gaps,
        current_b3_fallback_used=False,
        sector_classification_records=len(classifications),
        point_in_time_sector_classification_records=point_in_time_classifications,
        bank_profiles=len(bank_profiles),
        point_in_time_bank_profiles=point_in_time_bank_profiles,
        expected_ticker_years=len(expected_ticker_years),
        security_ticker_years=len(security_ticker_years & expected_ticker_years),
        price_ticker_years=len(price_ticker_years & expected_ticker_years),
        missing_security_ticker_years=_format_ticker_years(missing_security),
        missing_price_ticker_years=_format_ticker_years(missing_prices),
        price_bars=price_bars,
        adjusted_price_bars=adjusted_price_bars,
        unadjusted_price_bars=unadjusted_price_bars,
        blockers=ordered_blockers,
        strict_historical_backtest_data_ready=ready,
        walk_forward_data_ready=ready,
        point_in_time_eligible=ready,
    )


def _validate_historical_mode(
    *,
    coverage: FundamentalCoverageSummary,
    coverage_records: list[FundamentalCoverageRecord] | None,
    as_of: datetime | None,
) -> None:
    if as_of is None:
        return
    if as_of.tzinfo is None or as_of.utcoffset() is None:
        raise ValueError("historical readiness as_of must be timezone-aware")
    if coverage_records is None:
        raise ValueError(
            "historical readiness with as_of requires granular coverage_records"
        )
    if coverage.historical_as_of != as_of:
        raise ValueError(
            "historical readiness as_of does not match coverage historical_as_of"
        )
    if len(coverage_records) != coverage.company_years:
        raise ValueError(
            "historical readiness coverage_records do not match coverage company_years"
        )
    for record in coverage_records:
        if record.historical_as_of != as_of:
            raise ValueError(
                "historical readiness coverage record has mismatched historical_as_of: "
                f"{record.company_id}/{record.fiscal_year}"
            )
        if record.historical_model_route_admissible is None:
            raise ValueError(
                "historical readiness coverage record lacks historical route decision: "
                f"{record.company_id}/{record.fiscal_year}"
            )


def _historical_route_gaps(
    records: list[FundamentalCoverageRecord],
) -> list[HistoricalModelRouteGap]:
    gaps: list[HistoricalModelRouteGap] = []
    for record in sorted(records, key=lambda item: (item.company_id, item.fiscal_year)):
        if record.historical_model_route_admissible:
            continue
        blockers = list(record.historical_model_route_blockers)
        if not blockers:
            blockers = [HISTORICAL_MODEL_ROUTE_MISSING]
        gaps.append(
            HistoricalModelRouteGap(
                company_id=record.company_id,
                fiscal_year=record.fiscal_year,
                tickers=list(record.tickers),
                model_id=record.historical_model_route_model_id,
                available_from=record.historical_model_route_available_from,
                evidence_source=record.historical_model_route_evidence_source,
                source_document=record.historical_model_route_source_document,
                blockers=blockers,
            )
        )
    return gaps


def _fundamental_pit_gaps(
    records: list[FundamentalCoverageRecord],
) -> list[FundamentalPointInTimeGap]:
    gaps: list[FundamentalPointInTimeGap] = []
    for record in sorted(records, key=lambda item: (item.company_id, item.fiscal_year)):
        if record.point_in_time_critical_coverage == 1.0:
            continue
        causes: list[str] = []
        if record.missing_critical:
            causes.append(CRITICAL_INPUTS_MISSING)
        if record.untimed_critical:
            causes.append(CRITICAL_INPUTS_NOT_POINT_IN_TIME)
        if record.not_yet_available_critical:
            causes.append(CRITICAL_INPUTS_NOT_YET_AVAILABLE)
        if (
            record.applicability == "BANK_ACCOUNTING_CONTRACT_AVAILABLE"
            and record.untimed_critical
        ):
            causes.append(SPECIALIZED_EVIDENCE_NOT_POINT_IN_TIME)
        for route_blocker in record.historical_model_route_blockers:
            if route_blocker not in causes:
                causes.append(route_blocker)
        if not causes:
            causes.append(UNATTRIBUTED_POINT_IN_TIME_GAP)
        gaps.append(
            FundamentalPointInTimeGap(
                company_id=record.company_id,
                fiscal_year=record.fiscal_year,
                tickers=list(record.tickers),
                contract=record.contract,
                applicability=record.applicability,
                sector_model_id=record.sector_model_id,
                point_in_time_critical_coverage=record.point_in_time_critical_coverage,
                missing_critical=list(record.missing_critical),
                untimed_critical=list(record.untimed_critical),
                not_yet_available_critical=list(record.not_yet_available_critical),
                historical_model_route_blockers=list(
                    record.historical_model_route_blockers
                ),
                latest_available_from=record.latest_available_from,
                causes=causes,
            )
        )
    return gaps


def _ticker_years(
    dataset: BootstrapDataset,
    *,
    artifact_name: str,
) -> set[tuple[int, str]]:
    result: set[tuple[int, str]] = set()
    for artifact in dataset.manifest.artifacts:
        if artifact.name != artifact_name or artifact.reference_year is None:
            continue
        for row in _jsonl_rows(dataset.run_dir / artifact.path):
            ticker = str(row.get("ticker") or "").strip().upper()
            if ticker:
                result.add((artifact.reference_year, ticker))
    return result


def _price_rows(dataset: BootstrapDataset) -> list[tuple[int, str, bool]]:
    result: list[tuple[int, str, bool]] = []
    for artifact in dataset.manifest.artifacts:
        if artifact.name != "b3_cotahist" or artifact.reference_year is None:
            continue
        for row in _jsonl_rows(dataset.run_dir / artifact.path):
            ticker = str(row.get("ticker") or "").strip().upper()
            if not ticker:
                continue
            result.append(
                (
                    artifact.reference_year,
                    ticker,
                    row.get("adjusted_close") is not None,
                )
            )
    return result


def _jsonl_rows(path: Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    with gzip.open(path, "rt", encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            payload = line.strip()
            if not payload:
                continue
            item = json.loads(payload)
            if not isinstance(item, dict):
                raise TypeError(
                    f"historical readiness expected an object at {path}:{line_number}"
                )
            rows.append(item)
    return rows


def _format_ticker_years(items: list[tuple[int, str]]) -> list[str]:
    return [f"{ticker}:{year}" for year, ticker in items]
