from ultimate_stock_analyzer.fundamentals.metrics import (
    cagr,
    free_cash_flow,
    net_debt_to_ebitda,
    roe,
    roic,
)


def test_basic_financial_metrics() -> None:
    assert free_cash_flow(100.0, -30.0) == 70.0
    assert net_debt_to_ebitda(500.0, 100.0, 200.0) == 2.0
    assert round(roe(100.0, 900.0, 1100.0) or 0, 4) == 0.1
    assert round(roic(200.0, 0.25, 900.0, 1100.0) or 0, 4) == 0.15
    assert round(cagr(100.0, 121.0, 2) or 0, 4) == 0.1
