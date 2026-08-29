from __future__ import annotations

from datetime import date

from ultimate_stock_analyzer.backtesting.models import CashDistribution, PricePoint, ShareAction


def first_price_after(points: list[PricePoint], ticker: str, after: date) -> PricePoint | None:
    candidates = [point for point in points if point.ticker == ticker and point.trading_date > after]
    return min(candidates, key=lambda point: point.trading_date) if candidates else None


def total_holding_return(
    *,
    ticker: str,
    entry_decision_date: date,
    exit_decision_date: date,
    prices: list[PricePoint],
    share_actions: list[ShareAction] | None = None,
    distributions: list[CashDistribution] | None = None,
) -> float | None:
    """Compute total return using next-session prices and explicit corporate actions.

    Share-ratio and cash events are processed chronologically. When both occur on the same date,
    the share-ratio event is applied first; data preparation must flag a different contractual
    ordering instead of relying on this default.
    """
    entry = first_price_after(prices, ticker, entry_decision_date)
    exit_point = first_price_after(prices, ticker, exit_decision_date)
    if entry is None or exit_point is None or exit_point.trading_date <= entry.trading_date:
        return None

    events: list[tuple[date, int, float]] = []
    for event in share_actions or []:
        if event.ticker == ticker and entry.trading_date < event.ex_date <= exit_point.trading_date:
            events.append((event.ex_date, 0, event.ratio_new_per_old))
    for event in distributions or []:
        if event.ticker == ticker and entry.trading_date < event.ex_date <= exit_point.trading_date:
            events.append((event.ex_date, 1, event.amount_per_share))

    shares = 1.0
    cash = 0.0
    for _, event_kind, value in sorted(events):
        if event_kind == 0:
            shares *= value
        else:
            cash += shares * value

    ending_value = shares * exit_point.close + cash
    return ending_value / entry.close - 1.0
