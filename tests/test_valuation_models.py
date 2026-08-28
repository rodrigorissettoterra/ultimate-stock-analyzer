import pytest

from ultimate_stock_analyzer.valuation.models import (
    discounted_cash_flow_per_share,
    enterprise_multiple_value_per_share,
    equity_multiple_value_per_share,
    residual_income_per_share,
    two_stage_ddm_per_share,
)


def test_dcf_returns_positive_equity_value_and_requires_valid_terminal_spread() -> None:
    value = discounted_cash_flow_per_share(
        fcff0=100.0,
        growth_rates=[0.08, 0.07, 0.06, 0.05, 0.04],
        wacc=0.12,
        terminal_growth=0.03,
        net_debt=150.0,
        diluted_shares=50.0,
    )
    assert value > 0

    with pytest.raises(ValueError, match="greater than terminal_growth"):
        discounted_cash_flow_per_share(
            fcff0=100.0,
            growth_rates=[0.05],
            wacc=0.03,
            terminal_growth=0.03,
            net_debt=0.0,
            diluted_shares=10.0,
        )


def test_residual_income_equals_book_value_when_roe_equals_cost_of_equity() -> None:
    fair = residual_income_per_share(
        book_value_per_share=20.0,
        roe_path=[0.12, 0.12, 0.12, 0.12, 0.12],
        cost_of_equity=0.12,
        payout_ratio=0.50,
        terminal_roe=0.12,
        terminal_growth=0.03,
    )
    assert fair == pytest.approx(20.0)


def test_ddm_and_multiple_models_are_deterministic() -> None:
    ddm = two_stage_ddm_per_share(
        dividend0=2.0,
        growth_rates=[0.08, 0.07, 0.06, 0.05, 0.04],
        cost_of_equity=0.12,
        terminal_growth=0.03,
    )
    equity = equity_multiple_value_per_share(metric_per_share=3.0, target_multiple=8.0)
    enterprise = enterprise_multiple_value_per_share(
        operating_metric=500.0,
        target_multiple=6.0,
        net_debt=900.0,
        diluted_shares=100.0,
    )

    assert ddm > 0
    assert equity == pytest.approx(24.0)
    assert enterprise == pytest.approx(21.0)
