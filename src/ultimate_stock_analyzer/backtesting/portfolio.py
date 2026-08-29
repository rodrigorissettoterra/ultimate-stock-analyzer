from __future__ import annotations

from collections.abc import Iterable
from datetime import date
from itertools import pairwise

from ultimate_stock_analyzer.backtesting.models import (
    BacktestPolicy,
    BacktestResult,
    CashDistribution,
    PeriodObservation,
    PricePoint,
    ScoreSnapshot,
    ShareAction,
    UniverseMembership,
)
from ultimate_stock_analyzer.backtesting.point_in_time import rank_visible_scores
from ultimate_stock_analyzer.backtesting.returns import total_holding_return


def _target_weights(tickers: Iterable[str]) -> dict[str, float]:
    names = tuple(tickers)
    if not names:
        return {"__CASH__": 1.0}
    weight = 1.0 / len(names)
    return {ticker: weight for ticker in names}


def _post_return_weights(weights: dict[str, float], returns: dict[str, float]) -> dict[str, float]:
    values = {
        ticker: weight * (1.0 + returns.get(ticker, 0.0))
        for ticker, weight in weights.items()
    }
    total = sum(values.values())
    if total <= 0:
        return {"__CASH__": 1.0}
    return {ticker: value / total for ticker, value in values.items()}


def turnover_between(current: dict[str, float], target: dict[str, float]) -> float:
    names = set(current) | set(target)
    return 0.5 * sum(abs(target.get(name, 0.0) - current.get(name, 0.0)) for name in names)


def run_rebalance_backtest(
    *,
    rebalance_dates: list[date],
    score_snapshots: list[ScoreSnapshot],
    memberships: list[UniverseMembership],
    prices: list[PricePoint],
    benchmark_ticker: str,
    policy: BacktestPolicy,
    share_actions: list[ShareAction] | None = None,
    distributions: list[CashDistribution] | None = None,
) -> BacktestResult:
    if len(rebalance_dates) < 2:
        raise ValueError("at least two rebalance dates are required")
    dates = sorted(dict.fromkeys(rebalance_dates))
    if len(dates) < 2:
        raise ValueError("at least two unique rebalance dates are required")

    equity = policy.initial_capital
    current_weights = {"__CASH__": 1.0}
    periods: list[PeriodObservation] = []
    versions: set[str] = set()

    for decision_date, exit_decision_date in pairwise(dates):
        ranked = rank_visible_scores(
            score_snapshots,
            as_of=decision_date,
            memberships=memberships,
            top_n=policy.top_n,
            min_score=policy.min_investment_score,
        )
        selected = tuple(item.ticker for item in ranked)
        versions.update(item.model_version for item in ranked)
        target = _target_weights(selected)
        turnover = turnover_between(current_weights, target)

        asset_returns: dict[str, float] = {}
        for ticker in selected:
            value = total_holding_return(
                ticker=ticker,
                entry_decision_date=decision_date,
                exit_decision_date=exit_decision_date,
                prices=prices,
                share_actions=share_actions,
                distributions=distributions,
            )
            if value is None:
                if policy.strict_price_paths:
                    raise ValueError(
                        f"missing selected asset price path: {ticker} at {decision_date}"
                    )
                continue
            asset_returns[ticker] = value

        if selected and len(asset_returns) != len(selected):
            target = _target_weights(asset_returns)
            turnover = turnover_between(current_weights, target)

        gross_return = sum(
            target.get(ticker, 0.0) * value for ticker, value in asset_returns.items()
        )
        total_cost_bps = policy.transaction_cost_bps + policy.slippage_bps
        cost = turnover * total_cost_bps / 10_000.0
        period_return = gross_return - cost
        realized_weights = _post_return_weights(target, asset_returns)

        benchmark_return = total_holding_return(
            ticker=benchmark_ticker,
            entry_decision_date=decision_date,
            exit_decision_date=exit_decision_date,
            prices=prices,
            share_actions=share_actions,
            distributions=distributions,
        )
        if benchmark_return is None:
            raise ValueError(f"missing benchmark price path for {decision_date}")

        equity *= 1.0 + period_return
        periods.append(
            PeriodObservation(
                decision_date=decision_date,
                exit_decision_date=exit_decision_date,
                portfolio_return=period_return,
                benchmark_return=benchmark_return,
                turnover=turnover,
                selected=selected,
                asset_returns=asset_returns,
            )
        )
        current_weights = realized_weights

    return BacktestResult(
        periods=tuple(periods),
        ending_equity=equity,
        model_versions=tuple(sorted(versions)),
    )
