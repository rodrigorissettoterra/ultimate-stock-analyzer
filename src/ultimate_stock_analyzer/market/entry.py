from __future__ import annotations

import math
from collections.abc import Sequence


def simple_moving_average(values: Sequence[float], window: int) -> float | None:
    if window <= 0 or len(values) < window:
        return None
    tail = values[-window:]
    return sum(tail) / window


def rsi(values: Sequence[float], period: int = 14) -> float | None:
    if period <= 0 or len(values) < period + 1:
        return None
    changes = [values[i] - values[i - 1] for i in range(len(values) - period, len(values))]
    gains = sum(max(change, 0.0) for change in changes) / period
    losses = sum(abs(min(change, 0.0)) for change in changes) / period
    if losses == 0:
        return 100.0 if gains > 0 else 50.0
    relative_strength = gains / losses
    return 100.0 - (100.0 / (1.0 + relative_strength))


def annualized_volatility(daily_returns: Sequence[float], trading_days: int = 252) -> float | None:
    vals = [float(value) for value in daily_returns if math.isfinite(float(value))]
    if len(vals) < 2:
        return None
    mean = sum(vals) / len(vals)
    variance = sum((value - mean) ** 2 for value in vals) / (len(vals) - 1)
    return math.sqrt(variance) * math.sqrt(trading_days)


def max_drawdown(prices: Sequence[float]) -> float | None:
    if not prices:
        return None
    peak = prices[0]
    worst = 0.0
    for price in prices:
        peak = max(peak, price)
        if peak > 0:
            drawdown = price / peak - 1.0
            worst = min(worst, drawdown)
    return worst


def distance_from_ma(prices: Sequence[float], window: int = 200) -> float | None:
    ma = simple_moving_average(prices, window)
    if ma is None or ma == 0 or not prices:
        return None
    return prices[-1] / ma - 1.0


def volume_zscore(volumes: Sequence[float], window: int = 60) -> float | None:
    if len(volumes) < window + 1:
        return None
    history = list(volumes[-window - 1 : -1])
    current = volumes[-1]
    mean = sum(history) / len(history)
    variance = sum((value - mean) ** 2 for value in history) / max(1, len(history) - 1)
    std = math.sqrt(variance)
    if std == 0:
        return 0.0
    return (current - mean) / std


def speculation_risk(
    return_5d: float | None,
    return_20d: float | None,
    volume_z: float | None,
    valuation_percentile_expensiveness: float | None,
    material_event_support: float = 0.0,
) -> float:
    """Heuristic 0..100 speculation risk; deterministic and intentionally transparent."""
    r5 = max(0.0, min(1.0, (return_5d or 0.0) / 0.15))
    r20 = max(0.0, min(1.0, (return_20d or 0.0) / 0.30))
    volume_component = max(0.0, min(1.0, (volume_z or 0.0) / 4.0))
    expensive = max(
        0.0,
        min(1.0, (valuation_percentile_expensiveness or 0.0) / 100.0),
    )
    support = max(0.0, min(1.0, material_event_support))
    raw = 100.0 * (0.30 * r5 + 0.20 * r20 + 0.25 * volume_component + 0.25 * expensive)
    return max(0.0, min(100.0, raw * (1.0 - 0.65 * support)))
