from ultimate_stock_analyzer.risk.metrics import historical_cvar, historical_var


def test_var_and_cvar() -> None:
    returns = [-0.10, -0.05, -0.02, 0.0, 0.01, 0.02, 0.03, 0.04, 0.05, 0.06] * 10
    var = historical_var(returns, 0.95)
    cvar = historical_cvar(returns, 0.95)
    assert var is not None and var >= 0.05
    assert cvar is not None and cvar >= var
