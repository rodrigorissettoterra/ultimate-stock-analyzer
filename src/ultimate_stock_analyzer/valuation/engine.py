from __future__ import annotations

import math
import statistics
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any

import yaml


class ValuationStatus(StrEnum):
    DEEPLY_UNDERVALUED = "DEEPLY_UNDERVALUED"
    UNDERVALUED = "UNDERVALUED"
    FAIR = "FAIR"
    OVERVALUED = "OVERVALUED"
    VERY_OVERVALUED = "VERY_OVERVALUED"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


@dataclass(frozen=True, slots=True)
class ValuationEstimate:
    model_id: str
    fair_value_per_share: float
    confidence: float
    low_value_per_share: float | None = None
    high_value_per_share: float | None = None
    assumptions: dict[str, float | str] = field(default_factory=dict)
    provenance: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ValuationPolicy:
    model_family: str
    weights: dict[str, float]
    min_model_coverage: float
    min_confidence: float
    high_dispersion_threshold: float


@dataclass(frozen=True, slots=True)
class ValuationResult:
    ticker: str
    model_family: str
    current_price: float
    blended_fair_value: float | None
    fair_value_low: float | None
    fair_value_high: float | None
    margin_of_safety: float | None
    valuation_score: float
    data_coverage: float
    confidence: float
    rankable: bool
    status: ValuationStatus
    model_dispersion: float | None
    estimates: tuple[ValuationEstimate, ...]
    flags: tuple[str, ...] = ()
    model_version: str = ""


class ValuationConfig:
    def __init__(self, raw: dict[str, Any]) -> None:
        self.version = str(raw["version"])
        self.default_family = str(raw["default_family"])
        defaults = raw.get("defaults") or {}
        self._defaults = {
            "min_model_coverage": float(defaults.get("min_model_coverage", 0.50)),
            "min_confidence": float(defaults.get("min_confidence", 0.45)),
            "high_dispersion_threshold": float(defaults.get("high_dispersion_threshold", 0.35)),
        }
        self.policies: dict[str, ValuationPolicy] = {}
        for family, policy_raw in raw["families"].items():
            weights = {
                str(model): float(weight)
                for model, weight in policy_raw["weights"].items()
            }
            if not weights or sum(weights.values()) <= 0:
                raise ValueError(f"valuation family {family} has no positive model weights")
            self.policies[str(family)] = ValuationPolicy(
                model_family=str(family),
                weights=weights,
                min_model_coverage=float(
                    policy_raw.get("min_model_coverage", self._defaults["min_model_coverage"])
                ),
                min_confidence=float(
                    policy_raw.get("min_confidence", self._defaults["min_confidence"])
                ),
                high_dispersion_threshold=float(
                    policy_raw.get(
                        "high_dispersion_threshold",
                        self._defaults["high_dispersion_threshold"],
                    )
                ),
            )
        if self.default_family not in self.policies:
            raise ValueError("default valuation family is not defined")

    @classmethod
    def from_yaml(cls, path: str | Path) -> ValuationConfig:
        with Path(path).open("r", encoding="utf-8") as file:
            return cls(yaml.safe_load(file))

    def policy_for(self, model_family: str) -> ValuationPolicy:
        return self.policies.get(model_family, self.policies[self.default_family])


class ValuationEngine:
    """Combine explicit valuation estimates without hiding model disagreement."""

    def __init__(self, config: ValuationConfig) -> None:
        self.config = config

    def evaluate(
        self,
        *,
        ticker: str,
        current_price: float,
        model_family: str,
        estimates: list[ValuationEstimate],
    ) -> ValuationResult:
        price = float(current_price)
        if not math.isfinite(price) or price <= 0:
            raise ValueError("current_price must be a positive finite number")
        policy = self.config.policy_for(model_family)
        accepted = _accepted_estimates(estimates, policy)
        total_policy_weight = sum(policy.weights.values())
        available_weight = sum(policy.weights[item.model_id] for item in accepted)
        coverage = available_weight / total_policy_weight if total_policy_weight else 0.0

        if not accepted:
            return ValuationResult(
                ticker=ticker,
                model_family=policy.model_family,
                current_price=price,
                blended_fair_value=None,
                fair_value_low=None,
                fair_value_high=None,
                margin_of_safety=None,
                valuation_score=50.0,
                data_coverage=0.0,
                confidence=0.0,
                rankable=False,
                status=ValuationStatus.INSUFFICIENT_DATA,
                model_dispersion=None,
                estimates=(),
                flags=("NO_VALID_VALUATION_MODELS",),
                model_version=self.config.version,
            )

        effective_weights = [
            policy.weights[item.model_id] * item.confidence for item in accepted
        ]
        if sum(effective_weights) <= 0:
            effective_weights = [policy.weights[item.model_id] for item in accepted]

        fair_values = [item.fair_value_per_share for item in accepted]
        blended = _weighted_median(fair_values, effective_weights)
        low_values = [
            item.low_value_per_share
            if item.low_value_per_share is not None
            else item.fair_value_per_share
            for item in accepted
        ]
        high_values = [
            item.high_value_per_share
            if item.high_value_per_share is not None
            else item.fair_value_per_share
            for item in accepted
        ]
        fair_low = _weighted_median(low_values, effective_weights)
        fair_high = _weighted_median(high_values, effective_weights)
        if fair_low > fair_high:
            fair_low, fair_high = fair_high, fair_low

        dispersion = _relative_median_absolute_deviation(fair_values)
        base_confidence = (
            sum(policy.weights[item.model_id] * item.confidence for item in accepted)
            / available_weight
            if available_weight
            else 0.0
        )
        dispersion_penalty = max(0.40, 1.0 - min(1.0, dispersion))
        confidence = max(
            0.0,
            min(1.0, base_confidence * coverage * dispersion_penalty),
        )
        margin_of_safety = blended / price - 1.0
        score = margin_of_safety_score(margin_of_safety)

        flags: list[str] = []
        if coverage < policy.min_model_coverage:
            flags.append("LOW_VALUATION_MODEL_COVERAGE")
        if confidence < policy.min_confidence:
            flags.append("LOW_VALUATION_CONFIDENCE")
        if dispersion > policy.high_dispersion_threshold:
            flags.append("HIGH_VALUATION_MODEL_DISPERSION")

        rankable = (
            coverage >= policy.min_model_coverage
            and confidence >= policy.min_confidence
        )
        status = (
            _status_from_margin(margin_of_safety)
            if rankable
            else ValuationStatus.INSUFFICIENT_DATA
        )
        return ValuationResult(
            ticker=ticker,
            model_family=policy.model_family,
            current_price=price,
            blended_fair_value=blended,
            fair_value_low=fair_low,
            fair_value_high=fair_high,
            margin_of_safety=margin_of_safety,
            valuation_score=score,
            data_coverage=max(0.0, min(1.0, coverage)),
            confidence=confidence,
            rankable=rankable,
            status=status,
            model_dispersion=dispersion,
            estimates=tuple(accepted),
            flags=tuple(flags),
            model_version=self.config.version,
        )


def _accepted_estimates(
    estimates: list[ValuationEstimate],
    policy: ValuationPolicy,
) -> list[ValuationEstimate]:
    accepted: list[ValuationEstimate] = []
    seen: set[str] = set()
    for estimate in estimates:
        if estimate.model_id not in policy.weights:
            continue
        if estimate.model_id in seen:
            raise ValueError(f"duplicate valuation model: {estimate.model_id}")
        seen.add(estimate.model_id)
        fair = float(estimate.fair_value_per_share)
        confidence = float(estimate.confidence)
        if not math.isfinite(fair) or fair <= 0:
            continue
        if not math.isfinite(confidence) or not 0.0 <= confidence <= 1.0:
            continue
        if estimate.low_value_per_share is not None and estimate.low_value_per_share <= 0:
            continue
        if estimate.high_value_per_share is not None and estimate.high_value_per_share <= 0:
            continue
        accepted.append(estimate)
    return accepted


def _weighted_median(values: list[float], weights: list[float]) -> float:
    if not values or len(values) != len(weights):
        raise ValueError("values and weights must be non-empty and aligned")
    pairs = sorted(zip(values, weights, strict=True), key=lambda pair: pair[0])
    total = sum(max(0.0, weight) for _, weight in pairs)
    if total <= 0:
        return float(statistics.median(values))
    threshold = total / 2.0
    cumulative = 0.0
    for value, weight in pairs:
        cumulative += max(0.0, weight)
        if cumulative >= threshold:
            return float(value)
    return float(pairs[-1][0])


def _relative_median_absolute_deviation(values: list[float]) -> float:
    if len(values) <= 1:
        return 0.0
    median = float(statistics.median(values))
    if median == 0:
        return 0.0
    mad = float(statistics.median(abs(value - median) for value in values))
    return abs(mad / median)


def margin_of_safety_score(margin: float) -> float:
    """Map valuation margin to 0..100 without claiming return predictability."""
    anchors = (
        (-0.50, 0.0),
        (-0.25, 15.0),
        (0.00, 50.0),
        (0.15, 65.0),
        (0.30, 80.0),
        (0.50, 95.0),
        (0.75, 100.0),
    )
    if margin <= anchors[0][0]:
        return anchors[0][1]
    if margin >= anchors[-1][0]:
        return anchors[-1][1]
    for (left_x, left_y), (right_x, right_y) in zip(anchors, anchors[1:], strict=True):
        if left_x <= margin <= right_x:
            fraction = (margin - left_x) / (right_x - left_x)
            return left_y + fraction * (right_y - left_y)
    raise RuntimeError("margin score interpolation failed")


def _status_from_margin(margin: float) -> ValuationStatus:
    if margin >= 0.40:
        return ValuationStatus.DEEPLY_UNDERVALUED
    if margin >= 0.20:
        return ValuationStatus.UNDERVALUED
    if margin >= -0.10:
        return ValuationStatus.FAIR
    if margin >= -0.25:
        return ValuationStatus.OVERVALUED
    return ValuationStatus.VERY_OVERVALUED
