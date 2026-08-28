from datetime import date

from ultimate_stock_analyzer.dividends.regularity import DividendPayment, analyze_dividends


def test_regular_dividend_payer() -> None:
    payments = [
        DividendPayment(date(year, 5, 15), 1.0, "DIVIDEND")
        for year in range(2022, 2027)
    ] + [
        DividendPayment(date(year, 11, 15), 1.0, "JCP")
        for year in range(2022, 2027)
    ]
    profile = analyze_dividends(payments, date(2026, 12, 1), current_price=25.0)
    assert profile.years_paid == 5
    assert profile.qualifies_as_regular_payer
    assert profile.regularity_score >= 90
    assert profile.ttm_yield is not None
