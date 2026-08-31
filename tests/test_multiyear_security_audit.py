from datetime import UTC, date, datetime

from ultimate_stock_analyzer.domain.master import SecurityRecord
from ultimate_stock_analyzer.market.prices import PriceBar
from ultimate_stock_analyzer.universe.multiyear_security_audit import (
    audit_multiyear_fca_against_cotahist,
)


def _security(
    company_id: str,
    ticker: str,
    *,
    reference_date: date,
    security_type: str = "Ações Ordinárias",
    market: str = "Bolsa",
) -> SecurityRecord:
    return SecurityRecord(
        company_id=company_id,
        ticker=ticker,
        security_type=security_type,
        market=market,
        administrator="B3",
        reference_date=reference_date,
        version=1,
        collected_at=datetime(2026, 8, 31, tzinfo=UTC),
    )


def _bar(
    ticker: str,
    trade_date: date,
    *,
    specification: str = "ON",
) -> PriceBar:
    return PriceBar(
        ticker=ticker,
        trade_date=trade_date,
        open=10.0,
        high=11.0,
        low=9.0,
        close=10.5,
        volume=1_000_000.0,
        trades=100,
        quantity=100_000,
        isin=f"BR{ticker}000000",
        specification=specification,
    )


def test_multiyear_fca_recovers_exact_ticker_trade_without_using_current_market() -> None:
    report = audit_multiyear_fca_against_cotahist(
        ("cvm:1", "cvm:2", "cvm:3"),
        {
            2022: [
                _security(
                    "cvm:1",
                    "AAA3",
                    reference_date=date(2022, 5, 1),
                    market="Bolsa",
                ),
                _security("cvm:2", "BBB3", reference_date=date(2022, 5, 1)),
            ],
            2026: [
                _security(
                    "cvm:1",
                    "AAA3",
                    reference_date=date(2026, 2, 1),
                    market="Balcão",
                ),
            ],
        },
        (
            _bar("AAA3", date(2026, 8, 28)),
            _bar("AAA3", date(2026, 8, 31), specification="ON ED"),
        ),
        cotahist_year=2026,
    )

    by_company = {item.company_id: item for item in report.company_evidence}
    assert by_company["cvm:1"].status == "TRADED_EXACT_FCA_TICKER"
    assert by_company["cvm:1"].traded_tickers == ("AAA3",)
    assert by_company["cvm:1"].latest_trade_date == date(2026, 8, 31)
    assert by_company["cvm:2"].status == "NO_2026_SPOT_TRADE_FOR_EXACT_FCA_TICKER"
    assert by_company["cvm:3"].status == "NO_FCA_TICKER_HISTORY"

    ticker = next(item for item in report.ticker_evidence if item.ticker == "AAA3")
    assert ticker.latest_fca_year == 2026
    assert ticker.latest_fca_market == "Balcão"
    assert ticker.cotahist_trade_days == 2
    assert ticker.b3_specifications == ("ON", "ON ED")


def test_multiyear_fca_does_not_resolve_reused_ticker_identity() -> None:
    report = audit_multiyear_fca_against_cotahist(
        ("cvm:4",),
        {
            2022: [_security("cvm:4", "SHRD3", reference_date=date(2022, 1, 1))],
            2025: [_security("cvm:5", "SHRD3", reference_date=date(2025, 1, 1))],
        },
        (_bar("SHRD3", date(2026, 8, 31)),),
        cotahist_year=2026,
    )

    company = report.company_evidence[0]
    assert company.status == "ONLY_CONFLICTING_FCA_TICKERS"
    assert company.conflicting_tickers == ("SHRD3",)
    assert company.traded_tickers == ()
    assert report.ticker_identity_conflicts == {"SHRD3": ("cvm:4", "cvm:5")}


def test_multiyear_audit_ignores_bars_outside_requested_cotahist_year() -> None:
    report = audit_multiyear_fca_against_cotahist(
        ("cvm:1",),
        {2025: [_security("cvm:1", "AAA3", reference_date=date(2025, 1, 1))]},
        (_bar("AAA3", date(2025, 12, 30)),),
        cotahist_year=2026,
    )
    assert report.cotahist_matching_rows == 0
    assert report.company_evidence[0].status == "NO_2026_SPOT_TRADE_FOR_EXACT_FCA_TICKER"
