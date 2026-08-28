import pytest

from ultimate_stock_analyzer.risk.metrics import (
    historical_cvar,
    historical_var,
    max_drawdown,
    worst_period_return,
)


def test_downside_metrics_have_expected_semantics() -> None:
    prices = [100.0, 110.0, 90.0, 95.0, 70.0, 80.0]
    drawdown = max_drawdown(prices)
    assert drawdown == pytest.approx(70.0 / 110.0 - 1.0)
    assert worst_period_return(prices, 2) is not None

    returns = [0.01, -0.01, 0.02, -0.03, -0.08, 0.005, -0.015, 0.01]
    var95 = historical_var(returns, 0.95)
    cvar95 = historical_cvar(returns, 0.95)
    assert var95 is not None and cvar95 is not None
    assert cvar95 >= var95
