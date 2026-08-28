from __future__ import annotations

import math
import statistics
from collections.abc import Sequence

from ultimate_stock_analyzer.market.indicators import daily_returns


def max_drawdown(prices: Sequence[float]) -> float | None:
    if not prices:
        return None
    peak = float(prices[0])
    if peak <= 0:
        return None
    worst = 0.0
    for raw_price in prices:
        price = float(raw_price)
        if price <= 0:
            return None
        peak = max(peak, price)
        worst = min(worst, price / peak - 1.0)
    return worst


def annualized_volatility(returns: Sequence[float], periods_per_year: int = 252) -> float | None:
    if len(returns) < 2 or periods_per_year <= 0:
        return None
    return float(statistics.stdev(float(value) for value in returns)) * math.sqrt(periods_per_year)


def downside_deviation(
    returns: Sequence[float],
    *,
    target: float = 0.0,
    periods_per_year: int = 252,
) -> float | None:
    if not returns or periods_per_year <= 0:
        return None
    shortfalls = [min(0.0, float(value) - target) for value in returns]
    semivariance = sum(value * value for value in shortfalls) / len(shortfalls)
    return math.sqrt(semivariance) * math.sqrt(periods_per_year)


def historical_var(returns: Sequence[float], confidence: float = 0.95) -> float | None:
    if not returns:
        return None
    if not 0.0 < confidence < 1.0:
        raise ValueError("confidence must be between 0 and 1")
    quantile_return = _quantile([float(value) for value in returns], 1.0 - confidence)
    return max(0.0, -quantile_return)


def historical_cvar(returns: Sequence[float], confidence: float = 0.95) -> float | None:
    if not returns:
        return None
    if not 0.0 < confidence < 1.0:
        raise ValueError("confidence must be between 0 and 1")
    values = [float(value) for value in returns]
    threshold = _quantile(values, 1.0 - confidence)
    tail = [value for value in values if value <= threshold]
    if not tail:
        return historical_var(values, confidence)
    return max(0.0, -sum(tail) / len(tail))


def worst_period_return(prices: Sequence[float], periods: int = 20) -> float | None:
    if periods <= 0:
        raise ValueError("periods must be positive")
    if len(prices) <= periods:
        return None
    worst: float | None = None
    for index in range(periods, len(prices)):
        start = float(prices[index - periods])
        end = float(prices[index])
        if start <= 0:
            continue
        observed = end / start - 1.0
        worst = observed if worst is None else min(worst, observed)
    return worst


def downside_beta(asset_returns: Sequence[float], benchmark_returns: Sequence[float]) -> float | None:
    if len(asset_returns) != len(benchmark_returns) or len(asset_returns) < 2:
        return None
    pairs = [
        (float(asset), float(benchmark))
        for asset, benchmark in zip(asset_returns, benchmark_returns, strict=True)
        if float(benchmark) < 0.0
    ]
    if len(pairs) < 2:
        return None
    assets = [asset for asset, _ in pairs]
    benchmark = [value for _, value in pairs]
    benchmark_mean = statistics.mean(benchmark)
    asset_mean = statistics.mean(assets)
    covariance = sum(
        (asset - asset_mean) * (market - benchmark_mean)
        for asset, market in pairs
    ) / (len(pairs) - 1)
    variance = statistics.variance(benchmark)
    if variance <= 0:
        return None
    return covariance / variance


def price_returns(prices: Sequence[float]) -> list[float]:
    return daily_returns(prices)


def _quantile(values: list[float], probability: float) -> float:
    if not values:
        raise ValueError("values must not be empty")
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    fraction = position - lower
    return ordered[lower] + fraction * (ordered[upper] - ordered[lower])
