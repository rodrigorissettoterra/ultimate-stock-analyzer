from datetime import date
from pathlib import Path
from typing import Any

import pytest

from ultimate_stock_analyzer.orchestration.service import AnalyzerService
from ultimate_stock_analyzer.universe.current_equity_securities import (
    CurrentBrazilianEquityCompanyDecision,
    CurrentBrazilianEquitySecurityDecision,
    CurrentBrazilianEquitySecurityUniverseReport,
)
from ultimate_stock_analyzer.universe.eligibility import (
    classify_brazilian_equity_issuers,
)
from ultimate_stock_analyzer.universe.scoring_gate import (
    partition_current_analysis_rows,
)


def _eligibility():
    return classify_brazilian_equity_issuers(
        ("cvm:1", "cvm:2", "cvm:3", "cvm:4"),
        brazilian_public_company_ids=("cvm:1", "cvm:2", "cvm:4"),
        foreign_issuer_company_ids=("cvm:3", "cvm:4"),
    )


def _security_universe() -> CurrentBrazilianEquitySecurityUniverseReport:
    companies = (
        CurrentBrazilianEquityCompanyDecision(
            company_id="cvm:1",
            issuer_code="ONE",
            trading_name="ONE",
            issuer_status="ELIGIBLE_BRAZILIAN_PUBLIC_COMPANY",
            status="ELIGIBLE_CURRENT_BRAZILIAN_EQUITY",
            eligible=True,
            exact_security_codes=("ONE3", "ONE11"),
            eligible_security_codes=("ONE3",),
            excluded_security_codes=("ONE11",),
            reason="eligible core equity",
        ),
        CurrentBrazilianEquityCompanyDecision(
            company_id="cvm:2",
            issuer_code="TWO",
            trading_name="TWO",
            issuer_status="ELIGIBLE_BRAZILIAN_PUBLIC_COMPANY",
            status="ELIGIBLE_CURRENT_BRAZILIAN_EQUITY",
            eligible=True,
            exact_security_codes=("TWO3",),
            eligible_security_codes=("TWO3",),
            excluded_security_codes=(),
            reason="eligible core equity",
        ),
        CurrentBrazilianEquityCompanyDecision(
            company_id="cvm:3",
            issuer_code="FORE",
            trading_name="FOREIGN",
            issuer_status="EXCLUDED_FOREIGN_ISSUER",
            status="EXCLUDED_ISSUER_NOT_ELIGIBLE",
            eligible=False,
            exact_security_codes=("FORE11",),
            eligible_security_codes=(),
            excluded_security_codes=("FORE11",),
            reason="foreign issuer",
        ),
        CurrentBrazilianEquityCompanyDecision(
            company_id="cvm:4",
            issuer_code="CONFLICT",
            trading_name="CONFLICT",
            issuer_status="CONFLICTING_CVM_REGISTRY_CLASSIFICATION",
            status="EXCLUDED_ISSUER_NOT_ELIGIBLE",
            eligible=False,
            exact_security_codes=("CONFLICT3",),
            eligible_security_codes=(),
            excluded_security_codes=("CONFLICT3",),
            reason="issuer registry conflict",
        ),
    )
    securities = (
        CurrentBrazilianEquitySecurityDecision(
            company_id="cvm:1",
            code="ONE3",
            status="ELIGIBLE_CURRENT_CORE_EQUITY_SECURITY",
            eligible=True,
            security_kind="COMMON_SHARE",
            specifications=("ON",),
            trade_days=100,
            first_trade_date=date(2026, 1, 2),
            last_trade_date=date(2026, 8, 31),
            detail_isin="BRONE0ACNOR0",
            observed_isins=("BRONE0ACNOR0",),
            reason="eligible current common share",
        ),
        CurrentBrazilianEquitySecurityDecision(
            company_id="cvm:1",
            code="ONE11",
            status="EXCLUDED_NON_CORE_SECURITY_KIND",
            eligible=False,
            security_kind="SUBSCRIPTION_BONUS",
            specifications=("BONUS",),
            trade_days=10,
            first_trade_date=date(2026, 1, 2),
            last_trade_date=date(2026, 8, 31),
            detail_isin=None,
            observed_isins=(),
            reason="non-core traded security",
        ),
        CurrentBrazilianEquitySecurityDecision(
            company_id="cvm:2",
            code="TWO3",
            status="ELIGIBLE_CURRENT_CORE_EQUITY_SECURITY",
            eligible=True,
            security_kind="COMMON_SHARE",
            specifications=("ON",),
            trade_days=100,
            first_trade_date=date(2026, 1, 2),
            last_trade_date=date(2026, 8, 31),
            detail_isin="BRTWO0ACNOR0",
            observed_isins=("BRTWO0ACNOR0",),
            reason="eligible current common share",
        ),
    )
    return CurrentBrazilianEquitySecurityUniverseReport(
        candidate_company_ids=4,
        eligible_company_count=2,
        eligible_security_count=2,
        company_status_counts={
            "ELIGIBLE_CURRENT_BRAZILIAN_EQUITY": 2,
            "EXCLUDED_ISSUER_NOT_ELIGIBLE": 2,
        },
        security_status_counts={
            "ELIGIBLE_CURRENT_CORE_EQUITY_SECURITY": 2,
            "EXCLUDED_NON_CORE_SECURITY_KIND": 1,
        },
        eligible_company_ids=("cvm:1", "cvm:2"),
        eligible_security_codes=("ONE3", "TWO3"),
        company_decisions=companies,
        security_decisions=securities,
    )


def test_current_analysis_gate_keeps_only_eligible_rows_and_preserves_diagnostics() -> None:
    eligibility = _eligibility()
    rows = [
        {"company_id": "cvm:1", "ticker": "ONE3"},
        {"company_id": "cvm:3", "ticker": "FORE11"},
        {"company_id": "cvm:4", "ticker": "CONFLICT3"},
    ]

    eligible, report = partition_current_analysis_rows(
        rows,
        eligibility_report=eligibility,
    )

    assert [row["ticker"] for row in eligible] == ["ONE3"]
    assert report.analysis_rows == 3
    assert report.eligible_rows == 1
    assert report.excluded_rows == 2
    assert report.point_in_time_eligible is False
    assert report.scope == "CURRENT_STATE_ONLY"
    assert [item.company_id for item in report.exclusions] == ["cvm:3", "cvm:4"]
    assert report.exclusions[0].status == "EXCLUDED_FOREIGN_ISSUER"
    assert report.exclusions[1].status == "CONFLICTING_CVM_REGISTRY_CLASSIFICATION"


def test_current_analysis_gate_excludes_unresolved_identity() -> None:
    eligibility = classify_brazilian_equity_issuers(
        ("cvm:999",),
        brazilian_public_company_ids=(),
        foreign_issuer_company_ids=(),
    )

    eligible, report = partition_current_analysis_rows(
        ({"company_id": "cvm:999", "ticker": "MISS3"},),
        eligibility_report=eligibility,
    )

    assert eligible == []
    assert report.excluded_rows == 1
    assert report.exclusions[0].status == "UNRESOLVED_CVM_REGISTRY_CLASSIFICATION"


def test_current_analysis_gate_fails_closed_without_canonical_identity() -> None:
    with pytest.raises(ValueError, match="requires canonical company_id"):
        partition_current_analysis_rows(
            ({"ticker": "NOID3"},),
            eligibility_report=_eligibility(),
        )


def test_current_analysis_gate_fails_closed_without_eligibility_decision() -> None:
    with pytest.raises(ValueError, match="lacks a universe eligibility decision"):
        partition_current_analysis_rows(
            ({"company_id": "cvm:999", "ticker": "MISS3"},),
            eligibility_report=_eligibility(),
        )


def test_security_level_gate_requires_exact_ticker() -> None:
    with pytest.raises(ValueError, match="requires exact B3 security code"):
        partition_current_analysis_rows(
            ({"company_id": "cvm:1"},),
            eligibility_report=_eligibility(),
            security_universe_report=_security_universe(),
        )


def test_security_level_gate_excludes_non_core_and_unknown_company_ticker_pair() -> None:
    eligible, report = partition_current_analysis_rows(
        (
            {"company_id": "cvm:1", "ticker": "one3"},
            {"company_id": "cvm:1", "ticker": "ONE11"},
            {"company_id": "cvm:1", "ticker": "FAKE3"},
            {"company_id": "cvm:3", "ticker": "FORE11"},
        ),
        eligibility_report=_eligibility(),
        security_universe_report=_security_universe(),
    )

    assert eligible == [{"company_id": "cvm:1", "ticker": "ONE3"}]
    assert report.eligible_rows == 1
    assert report.excluded_rows == 3
    assert [item.status for item in report.exclusions] == [
        "EXCLUDED_SECURITY_NOT_IN_CURRENT_UNIVERSE",
        "EXCLUDED_NON_CORE_SECURITY_KIND",
        "EXCLUDED_FOREIGN_ISSUER",
    ]


def test_analyzer_service_filters_security_level_before_invoking_scoring_engine() -> None:
    root = Path(__file__).resolve().parents[1]
    service = AnalyzerService(root / "config/scoring/model_v0.1.yml")

    class CapturingEngine:
        def __init__(self) -> None:
            self.rows: list[dict[str, Any]] = []

        def score_universe(
            self,
            rows: list[dict[str, Any]],
            red_flags: object = None,
        ) -> list[Any]:
            self.rows = rows
            return []

    engine = CapturingEngine()
    service.engine = engine  # type: ignore[assignment]
    rows = [
        {"company_id": "cvm:1", "ticker": "ONE3"},
        {"company_id": "cvm:1", "ticker": "ONE11"},
        {"company_id": "cvm:2", "ticker": "TWO3"},
        {"company_id": "cvm:3", "ticker": "FORE11"},
    ]

    results, report = service.rank_current_brazilian_equities(
        rows,
        eligibility_report=_eligibility(),
        security_universe_report=_security_universe(),
    )

    assert results == []
    assert [(row["company_id"], row["ticker"]) for row in engine.rows] == [
        ("cvm:1", "ONE3"),
        ("cvm:2", "TWO3"),
    ]
    assert report.excluded_rows == 2
    assert {(item.company_id, item.ticker, item.status) for item in report.exclusions} == {
        ("cvm:1", "ONE11", "EXCLUDED_NON_CORE_SECURITY_KIND"),
        ("cvm:3", "FORE11", "EXCLUDED_FOREIGN_ISSUER"),
    }
