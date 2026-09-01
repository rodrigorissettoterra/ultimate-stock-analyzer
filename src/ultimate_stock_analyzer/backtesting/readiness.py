from __future__ import annotations

import gzip
import json
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, Field

from ultimate_stock_analyzer.bootstrap.coverage import FundamentalCoverageSummary
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


class HistoricalBacktestReadinessReport(BaseModel):
    schema_version: str = "1.0"
    effect: str = "diagnostic_only_no_scoring_or_weight_promotion"
    generated_at: datetime
    bootstrap_run_id: str
    bootstrap_manifest_sha256: str
    start_year: int
    end_year: int
    requested_tickers: list[str]
    source_policy: str

    fundamental_companies: int = Field(ge=0)
    fundamental_company_years: int = Field(ge=0)
    point_in_time_critical_complete_company_years: int = Field(ge=0)
    longitudinal_pair_ready_company_years: int = Field(ge=0)
    resolved_sector_model_company_years: int = Field(ge=0)
    specialized_contract_required_company_years: int = Field(ge=0)

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
) -> HistoricalBacktestReadinessReport:
    """Audit whether one bootstrap run can safely feed M15/M16 historical evaluation.

    This audit is deliberately fail-closed. Current-state sector labels, latest-state
    specialized accounting evidence and unadjusted price history remain visible as
    blockers rather than being retroactively treated as point-in-time evidence.
    """

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

    blockers: set[str] = set()
    if coverage.company_years == 0:
        blockers.add(NO_FUNDAMENTAL_COMPANY_YEARS)
    if coverage.point_in_time_critical_complete_company_years < coverage.company_years:
        blockers.add(FUNDAMENTAL_POINT_IN_TIME_COVERAGE_INCOMPLETE)
    if coverage.specialized_contract_required_company_years:
        blockers.add(SPECIALIZED_ACCOUNTING_CONTRACT_MISSING)

    if not classifications:
        blockers.add(SECTOR_ROUTING_UNAVAILABLE)
    elif point_in_time_classifications != len(classifications):
        blockers.add(SECTOR_ROUTING_NOT_POINT_IN_TIME)

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
        fundamental_companies=coverage.companies,
        fundamental_company_years=coverage.company_years,
        point_in_time_critical_complete_company_years=(
            coverage.point_in_time_critical_complete_company_years
        ),
        longitudinal_pair_ready_company_years=(
            coverage.longitudinal_pair_ready_company_years
        ),
        resolved_sector_model_company_years=(
            coverage.resolved_sector_model_company_years
        ),
        specialized_contract_required_company_years=(
            coverage.specialized_contract_required_company_years
        ),
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
