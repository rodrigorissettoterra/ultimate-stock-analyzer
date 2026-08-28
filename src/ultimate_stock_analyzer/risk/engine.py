from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from itertools import pairwise
from pathlib import Path
from typing import Any

import yaml

from ultimate_stock_analyzer.market.prices import PriceBar
from ultimate_stock_analyzer.risk.metrics import (
    annualized_volatility,
    downside_deviation,
    historical_cvar,
    historical_var,
    max_drawdown,
    price_returns,
    worst_period_return,
)


class RiskStatus(StrEnum):
    DEFENSIVE = "DEFENSIVE"
    MODERATE = "MODERATE"
    ELEVATED = "ELEVATED"
    VERY_HIGH = "VERY_HIGH"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


@dataclass(frozen=True, slots=True)
class RiskConfig:
    version: str
    weights: dict[str, float]
    min_history: int
    min_confidence: float

    @classmethod
    def from_yaml(cls, path: str | Path) -> RiskConfig:
        with Path(path).open("r", encoding="utf-8") as file:
            raw: dict[str, Any] = yaml.safe_load(file)
        weights = {str(name): float(weight) for name, weight in raw["risk_weights"].items()}
        if any(weight <= 0 for weight in weights.values()):
            raise ValueError("risk weights must be positive")
        return cls(
            version=str(raw["version"]),
            weights=weights,
            min_history=int(raw["risk_min_history"]),
            min_confidence=float(raw["risk_min_confidence"]),
        )


@dataclass(frozen=True, slots=True)
class RiskAnalysis:
    ticker: str
    risk_safety_score: float
    confidence: float
    rankable: bool
    status: RiskStatus
    metrics: dict[str, float | None]
    components: dict[str, float]
    flags: tuple[str, ...]
    model_version: str


def analyze_risk(bars: list[PriceBar], *, config: RiskConfig) -> RiskAnalysis:
    ordered = sorted(bars, key=lambda bar: bar.trade_date)
    if len(ordered) < 2:
        raise ValueError("at least two price bars are required")
    ticker = ordered[0].ticker
    if any(bar.ticker != ticker for bar in ordered):
        raise ValueError("all price bars must belong to one ticker")
    if any(left.trade_date == right.trade_date for left, right in pairwise(ordered)):
        raise ValueError("duplicate trade date in risk history")

    prices = [bar.analysis_close for bar in ordered]
    returns = price_returns(prices)
    drawdown = max_drawdown(prices)
    volatility = annualized_volatility(returns)
    downside = downside_deviation(returns)
    var95 = historical_var(returns, 0.95)
    cvar95 = historical_cvar(returns, 0.95)
    worst20 = worst_period_return(prices, 20)

    components: dict[str, float] = {}
    if drawdown is not None:
        components["drawdown"] = _risk_safety(-drawdown, ((0.0, 100.0), (0.15, 85.0), (0.30, 60.0), (0.50, 30.0), (0.70, 5.0)))
    if volatility is not None:
        components["volatility"] = _risk_safety(volatility, ((0.08, 100.0), (0.15, 90.0), (0.25, 70.0), (0.40, 40.0), (0.60, 15.0), (0.90, 0.0)))
    if cvar95 is not None:
        components["cvar95"] = _risk_safety(cvar95, ((0.005, 100.0), (0.015, 90.0), (0.03, 70.0), (0.05, 45.0), (0.08, 15.0), (0.12, 0.0)))
    if downside is not None:
        components["downside_deviation"] = _risk_safety(downside, ((0.05, 100.0), (0.10, 90.0), (0.18, 70.0), (0.30, 45.0), (0.45, 20.0), (0.65, 0.0)))
    if worst20 is not None:
        components["worst_20d"] = _risk_safety(-worst20, ((0.02, 100.0), (0.08, 90.0), (0.15, 70.0), (0.25, 45.0), (0.40, 15.0), (0.55, 0.0)))

    total_weight = sum(config.weights.values())
    available_weight = sum(config.weights[name] for name in components if name in config.weights)
    safety = (
        sum(components[name] * config.weights[name] for name in components if name in config.weights)
        / available_weight
        if available_weight
        else 50.0
    )
    coverage = available_weight / total_weight if total_weight else 0.0
    adjusted_fraction = sum(bar.is_adjusted for bar in ordered) / len(ordered)
    history_confidence = min(1.0, len(ordered) / max(config.min_history, 1))
    adjustment_confidence = 1.0 if adjusted_fraction >= 0.95 else 0.60
    confidence = max(0.0, min(1.0, coverage * history_confidence * adjustment_confidence))

    flags: list[str] = []
    if len(ordered) < config.min_history:
        flags.append("SHORT_RISK_HISTORY")
    if adjusted_fraction < 0.95:
        flags.append("UNADJUSTED_RISK_SERIES")
    if confidence < config.min_confidence:
        flags.append("LOW_RISK_CONFIDENCE")

    rankable = len(ordered) >= config.min_history and confidence >= config.min_confidence
    status = _risk_status(safety) if rankable else RiskStatus.INSUFFICIENT_DATA
    return RiskAnalysis(
        ticker=ticker,
        risk_safety_score=max(0.0, min(100.0, safety)),
        confidence=confidence,
        rankable=rankable,
        status=status,
        metrics={
            "max_drawdown": drawdown,
            "annualized_volatility": volatility,
            "downside_deviation": downside,
            "var_95_daily": var95,
            "cvar_95_daily": cvar95,
            "worst_return_20d": worst20,
        },
        components=components,
        flags=tuple(flags),
        model_version=config.version,
    )


def _risk_safety(value: float, anchors: tuple[tuple[float, float], ...]) -> float:
    if value <= anchors[0][0]:
        return anchors[0][1]
    if value >= anchors[-1][0]:
        return anchors[-1][1]
    for (left_x, left_y), (right_x, right_y) in pairwise(anchors):
        if left_x <= value <= right_x:
            fraction = (value - left_x) / (right_x - left_x)
            return left_y + fraction * (right_y - left_y)
    return 50.0


def _risk_status(score: float) -> RiskStatus:
    if score >= 80:
        return RiskStatus.DEFENSIVE
    if score >= 60:
        return RiskStatus.MODERATE
    if score >= 35:
        return RiskStatus.ELEVATED
    return RiskStatus.VERY_HIGH
