from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

import yaml

from ultimate_stock_analyzer.market.indicators import (
    daily_volatility,
    period_return,
    rsi,
    simple_moving_average,
    standardized_period_return,
    volume_ratio,
)
from ultimate_stock_analyzer.market.prices import PriceBar


class EntryStatus(StrEnum):
    FAVORABLE = "FAVORABLE"
    NEUTRAL = "NEUTRAL"
    WAIT = "WAIT"
    EXTENDED_SPECULATIVE = "EXTENDED_SPECULATIVE"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


@dataclass(frozen=True, slots=True)
class EntryConfig:
    version: str
    weights: dict[str, float]
    min_coverage: float
    min_confidence: float
    favorable_score: float
    wait_score: float
    high_speculation_risk: float

    @classmethod
    def from_yaml(cls, path: str | Path) -> EntryConfig:
        with Path(path).open("r", encoding="utf-8") as file:
            raw: dict[str, Any] = yaml.safe_load(file)
        weights = {str(key): float(value) for key, value in raw["weights"].items()}
        if any(value <= 0 for value in weights.values()):
            raise ValueError("entry component weights must be positive")
        return cls(
            version=str(raw["version"]),
            weights=weights,
            min_coverage=float(raw["min_coverage"]),
            min_confidence=float(raw["min_confidence"]),
            favorable_score=float(raw["thresholds"]["favorable_score"]),
            wait_score=float(raw["thresholds"]["wait_score"]),
            high_speculation_risk=float(raw["thresholds"]["high_speculation_risk"]),
        )


@dataclass(frozen=True, slots=True)
class EntryAnalysis:
    ticker: str
    current_price: float
    as_of: str
    entry_score: float
    speculation_risk: float
    confidence: float
    coverage: float
    rankable: bool
    status: EntryStatus
    components: dict[str, float]
    indicators: dict[str, float | None]
    flags: tuple[str, ...]
    model_version: str


def analyze_entry(
    bars: list[PriceBar],
    *,
    config: EntryConfig,
    valuation_score: float | None,
    valuation_confidence: float = 1.0,
    material_event_explained: bool | None = None,
) -> EntryAnalysis:
    ordered = _validate_bars(bars)
    closes = [bar.analysis_close for bar in ordered]
    volumes = [bar.volume for bar in ordered]
    current = closes[-1]
    sma50 = simple_moving_average(closes, 50)
    sma200 = simple_moving_average(closes, 200)
    rsi14 = rsi(closes, 14)
    return5 = period_return(closes, 5)
    return20 = period_return(closes, 20)
    return60 = period_return(closes, 60)
    sigma60 = daily_volatility(closes, 60)
    volume20 = volume_ratio(volumes, 20)
    z5 = standardized_period_return(closes, 5, sigma60)
    z20 = standardized_period_return(closes, 20, sigma60)
    distance_sma200 = current / sma200 - 1.0 if sma200 and sma200 > 0 else None
    high_52w = max(closes[-252:]) if len(closes) >= 60 else None
    drawdown_52w = current / high_52w - 1.0 if high_52w and high_52w > 0 else None

    speculation_risk = _speculation_risk(
        z5=z5,
        z20=z20,
        volume_ratio20=volume20,
        distance_sma200=distance_sma200,
        material_event_explained=material_event_explained,
    )
    components: dict[str, float] = {}
    reliability: dict[str, float] = {}
    if valuation_score is not None and math.isfinite(float(valuation_score)):
        components["valuation"] = _clamp(float(valuation_score))
        reliability["valuation"] = _clamp01(float(valuation_confidence))
    if distance_sma200 is not None:
        components["trend"] = _trend_score(distance_sma200, sma50, sma200)
        reliability["trend"] = 1.0
    if rsi14 is not None:
        components["rsi"] = _rsi_score(rsi14)
        reliability["rsi"] = 1.0
    if return20 is not None:
        components["pullback"] = _pullback_score(return20)
        reliability["pullback"] = 1.0
    components["speculation_safety"] = 100.0 - speculation_risk
    reliability["speculation_safety"] = 1.0

    total_weight = sum(config.weights.values())
    available_weight = sum(config.weights[name] for name in components if name in config.weights)
    coverage = available_weight / total_weight if total_weight else 0.0
    weighted_score = sum(
        components[name] * config.weights[name] * reliability[name]
        for name in components
        if name in config.weights
    )
    reliable_weight = sum(
        config.weights[name] * reliability[name]
        for name in components
        if name in config.weights
    )
    entry_score = weighted_score / reliable_weight if reliable_weight else 50.0

    recent_window = ordered[-200:] if len(ordered) >= 200 else ordered
    adjusted_fraction = (
        sum(bar.is_adjusted for bar in recent_window) / len(recent_window)
        if recent_window
        else 0.0
    )
    history_confidence = min(1.0, len(ordered) / 252.0)
    adjustment_confidence = 1.0 if adjusted_fraction >= 0.95 else 0.75
    reliable_coverage = reliable_weight / total_weight if total_weight else 0.0
    confidence = _clamp01(
        reliable_coverage * history_confidence * adjustment_confidence
    )

    flags: list[str] = []
    if adjusted_fraction < 0.95:
        flags.append("UNADJUSTED_PRICE_SERIES")
    if material_event_explained is None:
        flags.append("EVENT_CONTEXT_UNKNOWN")
    if speculation_risk >= config.high_speculation_risk:
        flags.append("HIGH_SPECULATION_RISK")
        if material_event_explained is not True:
            flags.append("UNEXPLAINED_PRICE_SPIKE")
    if coverage < config.min_coverage:
        flags.append("LOW_ENTRY_DATA_COVERAGE")
    if confidence < config.min_confidence:
        flags.append("LOW_ENTRY_CONFIDENCE")

    rankable = coverage >= config.min_coverage and confidence >= config.min_confidence
    if not rankable:
        status = EntryStatus.INSUFFICIENT_DATA
    elif speculation_risk >= config.high_speculation_risk:
        status = EntryStatus.EXTENDED_SPECULATIVE
    elif entry_score >= config.favorable_score:
        status = EntryStatus.FAVORABLE
    elif entry_score < config.wait_score:
        status = EntryStatus.WAIT
    else:
        status = EntryStatus.NEUTRAL

    return EntryAnalysis(
        ticker=ordered[-1].ticker,
        current_price=current,
        as_of=ordered[-1].trade_date.isoformat(),
        entry_score=_clamp(entry_score),
        speculation_risk=_clamp(speculation_risk),
        confidence=confidence,
        coverage=_clamp01(coverage),
        rankable=rankable,
        status=status,
        components=components,
        indicators={
            "sma50": sma50,
            "sma200": sma200,
            "rsi14": rsi14,
            "return_5d": return5,
            "return_20d": return20,
            "return_60d": return60,
            "daily_volatility_60d": sigma60,
            "volume_ratio_20d": volume20,
            "return_z_5d": z5,
            "return_z_20d": z20,
            "distance_sma200": distance_sma200,
            "drawdown_52w": drawdown_52w,
        },
        flags=tuple(flags),
        model_version=config.version,
    )


def _validate_bars(bars: list[PriceBar]) -> list[PriceBar]:
    if len(bars) < 2:
        raise ValueError("at least two price bars are required")
    ordered = sorted(bars, key=lambda bar: bar.trade_date)
    ticker = ordered[0].ticker
    dates = set()
    for bar in ordered:
        if bar.ticker != ticker:
            raise ValueError("all price bars must belong to the same ticker")
        if bar.trade_date in dates:
            raise ValueError("duplicate trade date in price history")
        dates.add(bar.trade_date)
        if bar.analysis_close <= 0 or bar.volume < 0:
            raise ValueError("price bars contain invalid prices or volume")
    return ordered


def _speculation_risk(
    *,
    z5: float | None,
    z20: float | None,
    volume_ratio20: float | None,
    distance_sma200: float | None,
    material_event_explained: bool | None,
) -> float:
    components: list[tuple[float, float]] = []
    if z5 is not None:
        components.append((_scaled_positive(z5, 1.5, 4.0), 0.30))
    if z20 is not None:
        components.append((_scaled_positive(z20, 1.5, 4.0), 0.25))
    if volume_ratio20 is not None:
        components.append((_scaled_positive(volume_ratio20, 1.5, 5.0), 0.25))
    if distance_sma200 is not None:
        components.append((_scaled_positive(distance_sma200, 0.15, 0.50), 0.20))
    if not components:
        return 50.0
    total_weight = sum(weight for _, weight in components)
    risk = sum(value * weight for value, weight in components) / total_weight
    if material_event_explained is True:
        risk *= 0.65
    return _clamp(risk)


def _scaled_positive(value: float, start: float, full: float) -> float:
    if value <= start:
        return 0.0
    if value >= full:
        return 100.0
    return 100.0 * (value - start) / (full - start)


def _trend_score(distance: float, sma50: float | None, sma200: float | None) -> float:
    anchors = (
        (-0.30, 15.0),
        (-0.15, 45.0),
        (-0.05, 70.0),
        (0.00, 85.0),
        (0.10, 95.0),
        (0.20, 60.0),
        (0.35, 20.0),
        (0.50, 0.0),
    )
    score = _piecewise(distance, anchors)
    if sma50 is not None and sma200 is not None and sma50 < sma200:
        score = max(0.0, score - 10.0)
    return score


def _rsi_score(value: float) -> float:
    anchors = (
        (15.0, 15.0),
        (25.0, 30.0),
        (40.0, 75.0),
        (50.0, 95.0),
        (60.0, 90.0),
        (70.0, 60.0),
        (80.0, 25.0),
        (90.0, 5.0),
    )
    return _piecewise(value, anchors)


def _pullback_score(return20: float) -> float:
    anchors = (
        (-0.30, 10.0),
        (-0.15, 55.0),
        (-0.05, 85.0),
        (0.05, 95.0),
        (0.10, 85.0),
        (0.15, 65.0),
        (0.25, 30.0),
        (0.40, 0.0),
    )
    return _piecewise(return20, anchors)


def _piecewise(value: float, anchors: tuple[tuple[float, float], ...]) -> float:
    if value <= anchors[0][0]:
        return anchors[0][1]
    if value >= anchors[-1][0]:
        return anchors[-1][1]
    for index in range(len(anchors) - 1):
        left_x, left_y = anchors[index]
        right_x, right_y = anchors[index + 1]
        if left_x <= value <= right_x:
            fraction = (value - left_x) / (right_x - left_x)
            return left_y + fraction * (right_y - left_y)
    return 50.0


def _clamp(value: float) -> float:
    return max(0.0, min(100.0, float(value)))


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))
