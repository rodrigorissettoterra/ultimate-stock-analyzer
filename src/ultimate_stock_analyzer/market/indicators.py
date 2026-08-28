from __future__ import annotations

import math
import statistics
from collections.abc import Sequence


def simple_moving_average(values: Sequence[float], window: int) -> float | None:
    if window <= 0:
        raise ValueError("window must be positive")
    if len(values) < window:
        return None
    selected = values[-window:]
    return sum(selected) / window


def period_return(values: Sequence[float], periods: int) -> float | None:
    if periods <= 0:
        raise ValueError("periods must be positive")
    if len(values) <= periods:
        return None
    start = float(values[-periods - 1])
    end = float(values[-1])
    if start <= 0:
        return None
    return end / start - 1.0


def daily_returns(values: Sequence[float]) -> list[float]:
    returns: list[float] = []
    for previous, current in zip(values, values[1:], strict=False):
        if previous <= 0:
            continue
        returns.append(float(current) / float(previous) - 1.0)
    return returns


def daily_volatility(values: Sequence[float], window: int = 60) -> float | None:
    returns = daily_returns(values)
    if len(returns) < 2:
        return None
    selected = returns[-window:] if len(returns) >= window else returns
    if len(selected) < 2:
        return None
    return float(statistics.stdev(selected))


def rsi(values: Sequence[float], period: int = 14) -> float | None:
    if period <= 0:
        raise ValueError("period must be positive")
    if len(values) <= period:
        return None
    changes = [
        float(current) - float(previous)
        for previous, current in zip(values[-period - 1 :], values[-period:], strict=True)
    ]
    gains = [max(change, 0.0) for change in changes]
    losses = [max(-change, 0.0) for change in changes]
    average_gain = sum(gains) / period
    average_loss = sum(losses) / period
    if average_loss == 0:
        return 100.0 if average_gain > 0 else 50.0
    relative_strength = average_gain / average_loss
    return 100.0 - 100.0 / (1.0 + relative_strength)


def volume_ratio(volumes: Sequence[float], window: int = 20) -> float | None:
    if window <= 0:
        raise ValueError("window must be positive")
    if len(volumes) <= window:
        return None
    baseline = volumes[-window - 1 : -1]
    average = sum(float(value) for value in baseline) / window
    if average <= 0:
        return None
    return float(volumes[-1]) / average


def standardized_period_return(
    values: Sequence[float],
    periods: int,
    daily_sigma: float | None,
) -> float | None:
    observed = period_return(values, periods)
    if observed is None or daily_sigma is None or daily_sigma <= 0:
        return None
    return observed / (daily_sigma * math.sqrt(periods))
