from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from typing import Any

from ultimate_stock_analyzer.backtesting.historical_event_dataset import (
    HistoricalEventAwareDataset,
    compare_raw_and_event_aware_m15,
)
from ultimate_stock_analyzer.backtesting.models import (
    BacktestPolicy,
    ScoreSnapshot,
    UniverseMembership,
)


def diagnostic_m15_comparison(
    *,
    dataset: HistoricalEventAwareDataset,
) -> dict[str, Any] | None:
    """Demonstrate M15 event handling without promoting historical readiness."""
    for action in dataset.share_actions:
        payload = _diagnostic_event_comparison(
            dataset=dataset,
            ticker=action.ticker,
            event_date=action.ex_date,
        )
        if payload is None:
            continue
        payload["event_kind"] = "share_action"
        payload["share_action_ex_date"] = action.ex_date.isoformat()
        payload["share_action_ratio_new_per_old"] = action.ratio_new_per_old
        return payload

    for distribution in dataset.distributions:
        if distribution.amount_per_share <= 0:
            continue
        payload = _diagnostic_event_comparison(
            dataset=dataset,
            ticker=distribution.ticker,
            event_date=distribution.ex_date,
        )
        if payload is None:
            continue
        payload["event_kind"] = "cash_distribution"
        payload["cash_distribution_ex_date"] = distribution.ex_date.isoformat()
        payload["cash_distribution_amount_per_share"] = distribution.amount_per_share
        return payload
    return None


def _diagnostic_event_comparison(
    *,
    dataset: HistoricalEventAwareDataset,
    ticker: str,
    event_date: date,
) -> dict[str, Any] | None:
    ticker_prices = sorted(
        (point for point in dataset.prices if point.ticker.upper() == ticker.upper()),
        key=lambda item: item.trading_date,
    )
    prior = [point for point in ticker_prices if point.trading_date < event_date]
    after = [point for point in ticker_prices if point.trading_date > event_date]
    if not prior or not after:
        return None

    entry_point = prior[-1]
    decision_date = entry_point.trading_date - timedelta(days=1)
    exit_decision_date = event_date
    if decision_date < dataset.start_date or exit_decision_date > dataset.end_date:
        return None

    available_at = datetime.combine(decision_date, time.min, tzinfo=UTC)
    comparison = compare_raw_and_event_aware_m15(
        dataset=dataset,
        rebalance_dates=[decision_date, exit_decision_date],
        score_snapshots=[
            ScoreSnapshot(
                ticker=ticker,
                reference_date=decision_date,
                available_at=available_at,
                investment_score=100.0,
                model_version="diagnostic-corporate-action-integration",
            )
        ],
        memberships=[
            UniverseMembership(
                ticker=ticker,
                start_date=dataset.start_date,
                end_date=dataset.end_date,
            )
        ],
        benchmark_ticker=ticker,
        policy=BacktestPolicy(
            top_n=1,
            transaction_cost_bps=0.0,
            slippage_bps=0.0,
        ),
    )
    raw_return = comparison.raw_result.periods[0].asset_returns[ticker]
    event_aware_return = comparison.event_aware_result.periods[0].asset_returns[ticker]
    payload = comparison.to_dict()
    payload["ticker"] = ticker
    payload["decision_date"] = decision_date.isoformat()
    payload["exit_decision_date"] = exit_decision_date.isoformat()
    payload["raw_asset_return"] = raw_return
    payload["event_aware_asset_return"] = event_aware_return
    return payload
