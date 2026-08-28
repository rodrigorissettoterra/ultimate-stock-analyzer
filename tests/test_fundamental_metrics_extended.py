from ultimate_stock_analyzer.fundamentals.metrics import (
    cash_conversion_cycle,
    current_ratio,
    days_inventory_outstanding,
    days_payables_outstanding,
    days_sales_outstanding,
    ebitda,
    effective_tax_rate,
    fcf_margin,
    gross_debt,
    liquid_funds,
    net_working_capital,
    quick_ratio,
    roa,
    roce,
    yoy_growth,
)


def test_profitability_liquidity_and_growth_metrics() -> None:
    assert yoy_growth(120, 100) == 0.2
    assert roa(12, 100, 140) == 0.1
    assert roce(20, 100, 30, 120, 40) == 20 / 75
    assert current_ratio(150, 100) == 1.5
    assert quick_ratio(150, 30, 100) == 1.2
    assert net_working_capital(150, 100) == 50
    assert fcf_margin(25, 200) == 0.125
    assert effective_tax_rate(-25, 100) == 0.25
    assert ebitda(150, -25) == 175
    assert gross_debt(100, 300) == 400
    assert liquid_funds(50, 20) == 70


def test_cash_conversion_cycle_components() -> None:
    dso = days_sales_outstanding(365, 30, 30)
    dio = days_inventory_outstanding(-365, 40, 40)
    dpo = days_payables_outstanding(-365, 20, 20)

    assert dso == 30
    assert dio == 40
    assert dpo == 20
    assert cash_conversion_cycle(dso, dio, dpo) == 50
