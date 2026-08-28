from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from ultimate_stock_analyzer.macro.models import (
    FactorState,
    MacroAnalysis,
    MacroFactor,
    MacroProfile,
    MacroSensitivity,
)


def load_macro_profile(path: str | Path, profile_name: str) -> MacroProfile:
    with Path(path).open("r", encoding="utf-8") as file:
        raw: dict[str, Any] = yaml.safe_load(file)
    profiles = raw.get("profiles", {})
    if profile_name not in profiles:
        raise KeyError(f"unknown macro profile: {profile_name}")
    payload = profiles[profile_name]
    sensitivities = tuple(
        MacroSensitivity(
            factor=MacroFactor(item["factor"]),
            coefficient=float(item["coefficient"]),
            weight=float(item["weight"]),
            rationale=str(item["rationale"]),
        )
        for item in payload["sensitivities"]
    )
    return MacroProfile(
        name=profile_name,
        version=str(raw["version"]),
        sensitivities=sensitivities,
        min_coverage=float(raw["min_coverage"]),
        min_confidence=float(raw["min_confidence"]),
    )


def analyze_macro_context(
    states: dict[MacroFactor, FactorState],
    *,
    profile: MacroProfile,
) -> MacroAnalysis:
    expected_weight = sum(item.weight for item in profile.sensitivities)
    available = [item for item in profile.sensitivities if item.factor in states]
    available_weight = sum(item.weight for item in available)
    coverage = available_weight / expected_weight if expected_weight else 0.0

    contributions: dict[str, float] = {}
    weighted_sum = 0.0
    confidence_sum = 0.0
    for sensitivity in available:
        state = states[sensitivity.factor]
        signed_effect = state.state_signal * sensitivity.coefficient
        contributions[sensitivity.factor.value] = signed_effect
        weighted_sum += signed_effect * sensitivity.weight
        confidence_sum += state.confidence * sensitivity.weight

    normalized_effect = weighted_sum / available_weight if available_weight else 0.0
    score = 50.0 + 50.0 * max(-1.0, min(1.0, normalized_effect))
    data_confidence = confidence_sum / available_weight if available_weight else 0.0
    confidence = data_confidence * coverage
    flags: list[str] = []
    if coverage < profile.min_coverage:
        flags.append("LOW_MACRO_FACTOR_COVERAGE")
    if confidence < profile.min_confidence:
        flags.append("LOW_MACRO_CONFIDENCE")

    return MacroAnalysis(
        profile=profile.name,
        score=max(0.0, min(100.0, score)),
        coverage=max(0.0, min(1.0, coverage)),
        confidence=max(0.0, min(1.0, confidence)),
        rankable=coverage >= profile.min_coverage and confidence >= profile.min_confidence,
        contributions=contributions,
        states={factor.value: state for factor, state in states.items()},
        flags=tuple(flags),
        model_version=profile.version,
    )


def analyze_macro_scenario(
    shocks: dict[MacroFactor, float],
    *,
    profile: MacroProfile,
) -> float:
    """Score an explicit normalized scenario; shock values must lie in [-1, 1]."""
    weighted_sum = 0.0
    weight = 0.0
    for sensitivity in profile.sensitivities:
        if sensitivity.factor not in shocks:
            continue
        shock = float(shocks[sensitivity.factor])
        if not -1.0 <= shock <= 1.0:
            raise ValueError("macro scenario shocks must be between -1 and 1")
        weighted_sum += shock * sensitivity.coefficient * sensitivity.weight
        weight += sensitivity.weight
    if weight == 0:
        return 50.0
    effect = max(-1.0, min(1.0, weighted_sum / weight))
    return 50.0 + 50.0 * effect
