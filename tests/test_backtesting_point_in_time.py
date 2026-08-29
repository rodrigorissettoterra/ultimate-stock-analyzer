from datetime import UTC, date, datetime

import pytest

from ultimate_stock_analyzer.backtesting.models import (
    BacktestPolicy,
    CashDistribution,
    PricePoint,
    ScoreSnapshot,
    ShareAction,
    UniverseMembership,
)
from ultimate_stock_analyzer.backtesting.point_in_time import latest_visible_scores
from ultimate_stock_analyzer.backtesting.portfolio import run_rebalance_backtest
from ultimate_stock_analyzer.backtesting.returns import total_holding_return


def test_future_revision_is_not_visible_and_delisted_company_remains_historical() -> None:
    snapshots = [
        ScoreSnapshot("OLD3", date(2024, 3, 31), datetime(2024, 5, 1, tzinfo=UTC), 80.0),
        ScoreSnapshot("OLD3", date(2024, 3, 31), datetime(2024, 8, 1, tzinfo=UTC), 20.0),
    ]
    memberships = [UniverseMembership("OLD3", date(2020, 1, 1), date(2024, 12, 31))]
    visible = latest_visible_scores(snapshots, as_of=date(2024, 6, 1), memberships=memberships)
    assert visible["OLD3"].investment_score == 80.0


def test_share_action_and_cash_distribution_are_in_total_return() -> None:
    prices = [
        PricePoint("AAA3", date(2024, 1, 2), 100.0),
        PricePoint("AAA3", date(2024, 2, 2), 55.0),
    ]
    result = total_holding_return(
        ticker="AAA3",
        entry_decision_date=date(2024, 1, 1),
        exit_decision_date=date(2024, 2, 1),
        prices=prices,
        share_actions=[ShareAction("AAA3", date(2024, 1, 15), 2.0)],
        distributions=[CashDistribution("AAA3", date(2024, 1, 20), 1.0)],
    )
    assert result == pytest.approx(0.12)


def test_backtest_uses_next_session_and_charges_turnover_cost() -> None:
    snapshots = [
        ScoreSnapshot("AAA3", date(2023, 12, 31), datetime(2024, 1, 1, tzinfo=UTC), 90.0),
    ]
    memberships = [UniverseMembership("AAA3", date(2020, 1, 1))]
    prices = [
        PricePoint("AAA3", date(2024, 1, 2), 100.0),
        PricePoint("AAA3", date(2024, 2, 2), 110.0),
        PricePoint("IBOV", date(2024, 1, 2), 100.0),
        PricePoint("IBOV", date(2024, 2, 2), 105.0),
    ]
    result = run_rebalance_backtest(
        rebalance_dates=[date(2024, 1, 1), date(2024, 2, 1)],
        score_snapshots=snapshots,
        memberships=memberships,
        prices=prices,
        benchmark_ticker="IBOV",
        policy=BacktestPolicy(top_n=1, transaction_cost_bps=10.0),
    )
    assert result.periods[0].portfolio_return == pytest.approx(0.099)
    assert result.periods[0].benchmark_return == pytest.approx(0.05)
    assert result.periods[0].turnover == pytest.approx(1.0)
