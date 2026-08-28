from __future__ import annotations

import math
import statistics
from dataclasses import dataclass
from enum import StrEnum
from itertools import pairwise
from pathlib import Path
from typing import Any

import yaml

from ultimate_stock_analyzer.market.prices import PriceBar


class LiquidityStatus(StrEnum):
    EXCELLENT = "EXCELLENT"
    GOOD = "GOOD"
    MODERATE = "MODERATE"
    LOW = "LOW"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


@dataclass(frozen=True, slots=True)
class LiquidityConfig:
    version: str
    weights: dict[str, float]
    min_history: int
    min_coverage: float

    @classmethod
    def from_yaml(cls, path: str | Path) -> LiquidityConfig:
        with Path(path).open("r", encoding="utf-8") as file:
            raw: dict[str, Any] = yaml.safe_load(file)
        weights = {str(name): float(weight) for name, weight in raw["liquidity_weights"].items()}
        if any(weight <= 0 for weight in weights.values()):
            raise ValueError("liquidity weights must be positive")
        return cls(
            version=str(raw["version"]),
            weights=weights,
            min_history=int(raw["liquidity_min_history"]),
            min_coverage=float(raw["liquidity_min_coverage"]),
        )


@dataclass(frozen=True, slots=True)
class LiquidityAnalysis:
    ticker: str
    liquidity_score: float
    coverage: float
    rankable: bool
    status: LiquidityStatus
    metrics: dict[str, float | None]
    components: dict[str, float]
    flags: tuple[str, ...]
    model_version: str


def analyze_liquidity(
    bars: list[PriceBar],
    *,
    config: LiquidityConfig,
    free_float_shares: float | None = None,
) -> LiquidityAnalysis:
    ordered = sorted(bars, key=lambda bar: bar.trade_date)
    if not ordered:
        raise ValueError("price bars are required")
    ticker = ordered[0].ticker
    if any(bar.ticker != ticker for bar in ordered):
        raise ValueError("all price bars must belong to one ticker")
    if any(left.trade_date == right.trade_date for left, right in pairwise(ordered)):
        raise ValueError("duplicate trade date in liquidity history")

    window60 = ordered[-60:]
    window20 = ordered[-20:]
    adtv20 = _mean([bar.volume for bar in window20])
    adtv60 = _mean([bar.volume for bar in window60])
    median_trades20 = _median([float(bar.trades) for bar in window20])
    zero_volume_fraction60 = (
        sum(bar.volume <= 0 for bar in window60) / len(window60) if window60 else None
    )
    latest = ordered[-1]
    spread = _spread_percent(latest.best_bid, latest.best_ask)
    free_float_turnover20: float | None = None
    if free_float_shares is not None:
        shares = float(free_float_shares)
        if math.isfinite(shares) and shares > 0:
            average_quantity = _mean([float(bar.quantity) for bar in window20])
            if average_quantity is not None:
                free_float_turnover20 = average_quantity / shares

    components: dict[str, float] = {}
    if adtv60 is not None:
        components["adtv"] = _increasing_score(adtv60, ((50_000.0, 5.0), (250_000.0, 20.0), (1_000_000.0, 40.0), (5_000_000.0, 65.0), (20_000_000.0, 85.0), (100_000_000.0, 100.0)))
    if median_trades20 is not None:
        components["trades"] = _increasing_score(median_trades20, ((10.0, 5.0), (50.0, 25.0), (200.0, 50.0), (1_000.0, 80.0), (5_000.0, 100.0)))
    if spread is not None:
        components["spread"] = _decreasing_score(spread, ((0.001, 100.0), (0.003, 90.0), (0.005, 80.0), (0.01, 60.0), (0.02, 35.0), (0.05, 5.0), (0.10, 0.0)))
    if zero_volume_fraction60 is not None:
        components["continuity"] = _decreasing_score(zero_volume_fraction60, ((0.0, 100.0), (0.05, 80.0), (0.10, 50.0), (0.25, 10.0), (0.50, 0.0)))
    if free_float_turnover20 is not None:
        components["turnover"] = _increasing_score(free_float_turnover20, ((0.0001, 10.0), (0.0005, 30.0), (0.001, 50.0), (0.003, 75.0), (0.01, 100.0)))

    total_weight = sum(config.weights.values())
    available_weight = sum(config.weights[name] for name in components if name in config.weights)
    score = (
        sum(components[name] * config.weights[name] for name in components if name in config.weights)
        / available_weight
        if available_weight
        else 0.0
    )
    coverage = available_weight / total_weight if total_weight else 0.0
    flags: list[str] = []
    if spread is None:
        flags.append("SPREAD_UNAVAILABLE")
    if free_float_turnover20 is None:
        flags.append("FREE_FLOAT_TURNOVER_UNAVAILABLE")
    if len(ordered) < config.min_history:
        flags.append("SHORT_LIQUIDITY_HISTORY")
    if coverage < config.min_coverage:
        flags.append("LOW_LIQUIDITY_DATA_COVERAGE")

    rankable = len(ordered) >= config.min_history and coverage >= config.min_coverage
    status = _liquidity_status(score) if rankable else LiquidityStatus.INSUFFICIENT_DATA
    return LiquidityAnalysis(
        ticker=ticker,
        liquidity_score=max(0.0, min(100.0, score)),
        coverage=max(0.0, min(1.0, coverage)),
        rankable=rankable,
        status=status,
        metrics={
            "adtv_20": adtv20,
            "adtv_60": adtv60,
            "median_trades_20": median_trades20,
            "spread_pct_latest": spread,
            "zero_volume_fraction_60": zero_volume_fraction60,
            "free_float_turnover_20": free_float_turnover20,
        },
        components=components,
        flags=tuple(flags),
        model_version=config.version,
    )


def days_to_liquidate(
    position_value: float,
    adtv: float,
    *,
    max_participation_rate: float = 0.10,
) -> float:
    position = float(position_value)
    daily_volume = float(adtv)
    participation = float(max_participation_rate)
    if position < 0 or daily_volume <= 0 or not 0 < participation <= 1:
        raise ValueError("invalid position, ADTV or participation rate")
    return position / (daily_volume * participation)


def _spread_percent(bid: float | None, ask: float | None) -> float | None:
    if bid is None or ask is None or bid <= 0 or ask <= 0 or ask < bid:
        return None
    midpoint = (bid + ask) / 2.0
    return (ask - bid) / midpoint if midpoint > 0 else None


def _mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def _median(values: list[float]) -> float | None:
    return float(statistics.median(values)) if values else None


def _increasing_score(value: float, anchors: tuple[tuple[float, float], ...]) -> float:
    return _piecewise(value, anchors)


def _decreasing_score(value: float, anchors: tuple[tuple[float, float], ...]) -> float:
    return _piecewise(value, anchors)


def _piecewise(value: float, anchors: tuple[tuple[float, float], ...]) -> float:
    if value <= anchors[0][0]:
        return anchors[0][1]
    if value >= anchors[-1][0]:
        return anchors[-1][1]
    for (left_x, left_y), (right_x, right_y) in pairwise(anchors):
        if left_x <= value <= right_x:
            fraction = (value - left_x) / (right_x - left_x)
            return left_y + fraction * (right_y - left_y)
    return 50.0


def _liquidity_status(score: float) -> LiquidityStatus:
    if score >= 80:
        return LiquidityStatus.EXCELLENT
    if score >= 60:
        return LiquidityStatus.GOOD
    if score >= 35:
        return LiquidityStatus.MODERATE
    return LiquidityStatus.LOW
