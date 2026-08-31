from datetime import UTC, date, datetime

import pytest

from ultimate_stock_analyzer.domain.master import SecurityRecord
from ultimate_stock_analyzer.universe.eligibility import (
    classify_brazilian_equity_issuers,
)
from ultimate_stock_analyzer.universe.security_eligibility import (
    classify_current_brazilian_equity_securities,
)


def _security(
    company_id: str,
    ticker: str,
    security_type: str,
    *,
    market: str = "Bolsa",
    administrator: str = "B3",
    trading_end: date | None = None,
) -> SecurityRecord:
    return SecurityRecord(
        company_id=company_id,
        ticker=ticker,
        security_type=security_type,
        market=market,
        administrator=administrator,
        trading_start=date(2020, 1, 1),
        trading_end=trading_end,
        reference_date=date(2026, 1, 1),
        version=1,
        collected_at=datetime(2026, 8, 31, tzinfo=UTC),
    )


def _issuer_report():
    return classify_brazilian_equity_issuers(
        ("cvm:1", "cvm:2", "cvm:3", "cvm:4"),
        brazilian_public_company_ids=("cvm:1", "cvm:2", "cvm:4"),
        foreign_issuer_company_ids=("cvm:3",),
    )


def test_current_security_eligibility_accepts_on_pn_and_units_only_after_all_gates() -> None:
    securities = [
        _security("cvm:1", "ONE3", "Ações Ordinárias"),
        _security("cvm:1", "ONE4", "Ações Preferenciais"),
        _security("cvm:1", "ONE11", "Units"),
        _security("cvm:1", "ONE12", "Bônus de Subscrição"),
        _security("cvm:2", "OTC3", "Ações Ordinárias", market="Balcão Organizado"),
        _security("cvm:3", "FORE3", "Ações Ordinárias"),
        _security("cvm:4", "OLD3", "Ações Ordinárias", trading_end=date(2026, 1, 31)),
    ]

    eligible, report = classify_current_brazilian_equity_securities(
        ("cvm:1", "cvm:2", "cvm:3", "cvm:4"),
        securities,
        issuer_eligibility_report=_issuer_report(),
        as_of=date(2026, 8, 31),
    )

    assert [security.ticker for security in eligible] == ["ONE11", "ONE3", "ONE4"]
    assert report.eligible_company_ids == ("cvm:1",)
    assert report.company_status_counts == {
        "ELIGIBLE_BRAZILIAN_LISTED_EQUITY_ISSUER": 1,
        "EXCLUDED_ISSUER_NOT_ELIGIBLE": 1,
        "EXCLUDED_NO_ELIGIBLE_B3_EQUITY_SECURITY": 2,
    }
    assert report.security_status_counts == {
        "ELIGIBLE_BRAZILIAN_LISTED_EQUITY_SECURITY": 3,
        "EXCLUDED_INACTIVE_SECURITY": 1,
        "EXCLUDED_ISSUER_NOT_ELIGIBLE": 1,
        "EXCLUDED_NON_EXCHANGE_MARKET": 1,
        "EXCLUDED_UNSUPPORTED_SECURITY_TYPE": 1,
    }
    assert report.point_in_time_eligible is False


def test_current_security_eligibility_fails_closed_when_fca_rows_are_absent() -> None:
    eligible, report = classify_current_brazilian_equity_securities(
        ("cvm:1", "cvm:2"),
        (_security("cvm:1", "ONE3", "Ações Ordinárias"),),
        issuer_eligibility_report=_issuer_report(),
        as_of=date(2026, 8, 31),
    )

    assert [security.ticker for security in eligible] == ["ONE3"]
    decisions = {decision.company_id: decision for decision in report.company_decisions}
    assert decisions["cvm:2"].status == "EXCLUDED_NO_FCA_SECURITY_ROWS"
    assert decisions["cvm:2"].eligible is False


def test_current_security_eligibility_requires_issuer_decision() -> None:
    with pytest.raises(ValueError, match="lack issuer eligibility decisions"):
        classify_current_brazilian_equity_securities(
            ("cvm:999",),
            (),
            issuer_eligibility_report=_issuer_report(),
            as_of=date(2026, 8, 31),
        )
