from __future__ import annotations

from datetime import UTC, date, datetime

from ultimate_stock_analyzer.backtesting.readiness import (
    CRITICAL_INPUTS_MISSING,
    CRITICAL_INPUTS_NOT_POINT_IN_TIME,
    SPECIALIZED_EVIDENCE_NOT_POINT_IN_TIME,
    _fundamental_pit_gaps,
)
from ultimate_stock_analyzer.bootstrap.coverage import FundamentalCoverageRecord

NOW = datetime(2026, 9, 2, tzinfo=UTC)


def _record(
    *,
    company_id: str,
    fiscal_year: int,
    ticker: str,
    applicability: str,
    contract: str,
    point_in_time_coverage: float,
    missing: list[str] | None = None,
    untimed: list[str] | None = None,
    sector_model_id: str | None = None,
) -> FundamentalCoverageRecord:
    return FundamentalCoverageRecord(
        company_id=company_id,
        cvm_code=int(company_id.split(":")[1]),
        company_name=f"Company {company_id}",
        tickers=[ticker],
        reference_date=date(fiscal_year, 12, 31),
        fiscal_year=fiscal_year,
        contract=contract,
        applicability=applicability,
        sector_model_id=sector_model_id,
        extracted_accounts=8,
        critical_coverage=1.0 if not missing else 0.8,
        total_coverage=1.0 if not missing else 0.9,
        point_in_time_critical_coverage=point_in_time_coverage,
        missing_critical=missing or [],
        missing_supporting=[],
        untimed_critical=untimed or [],
        source_documents=["TEST"],
        latest_available_from=None,
    )


def test_bank_latest_state_gap_is_attributed_to_specialized_evidence() -> None:
    gaps = _fundamental_pit_gaps(
        [
            _record(
                company_id="cvm:19348",
                fiscal_year=2025,
                ticker="ITUB4",
                applicability="BANK_ACCOUNTING_CONTRACT_AVAILABLE",
                contract="bank_prudential_v1",
                sector_model_id="banks",
                point_in_time_coverage=0.0,
                untimed=["roe", "tier1_capital_ratio"],
            )
        ]
    )

    assert len(gaps) == 1
    gap = gaps[0]
    assert gap.company_id == "cvm:19348"
    assert gap.fiscal_year == 2025
    assert gap.tickers == ["ITUB4"]
    assert gap.missing_critical == []
    assert gap.untimed_critical == ["roe", "tier1_capital_ratio"]
    assert gap.causes == [
        CRITICAL_INPUTS_NOT_POINT_IN_TIME,
        SPECIALIZED_EVIDENCE_NOT_POINT_IN_TIME,
    ]


def test_general_gap_distinguishes_missing_from_untimed_inputs() -> None:
    gaps = _fundamental_pit_gaps(
        [
            _record(
                company_id="cvm:9512",
                fiscal_year=2024,
                ticker="TEST3",
                applicability="GENERAL_CORPORATE_APPLICABLE",
                contract="general_corporate_v1",
                sector_model_id="general_corporate",
                point_in_time_coverage=0.5,
                missing=["operating_cash_flow"],
                untimed=["net_income"],
            ),
            _record(
                company_id="cvm:9512",
                fiscal_year=2025,
                ticker="TEST3",
                applicability="GENERAL_CORPORATE_APPLICABLE",
                contract="general_corporate_v1",
                sector_model_id="general_corporate",
                point_in_time_coverage=1.0,
            ),
        ]
    )

    assert len(gaps) == 1
    assert gaps[0].fiscal_year == 2024
    assert gaps[0].causes == [
        CRITICAL_INPUTS_MISSING,
        CRITICAL_INPUTS_NOT_POINT_IN_TIME,
    ]
