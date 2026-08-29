from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True, slots=True)
class DataConfidenceInputs:
    completeness: float | None = None
    freshness: float | None = None
    official_source_share: float | None = None
    consistency: float | None = None
    point_in_time_lineage: float | None = None


@dataclass(frozen=True, slots=True)
class DataConfidenceConfig:
    weights: dict[str, float]
    min_coverage: float
    min_score: float
    version: str

    @classmethod
    def from_yaml(cls, path: str | Path) -> DataConfidenceConfig:
        with Path(path).open("r", encoding="utf-8") as file:
            raw: dict[str, Any] = yaml.safe_load(file)
        weights = {str(key): float(value) for key, value in raw["data_confidence_weights"].items()}
        if any(weight <= 0 for weight in weights.values()):
            raise ValueError("data-confidence weights must be positive")
        return cls(
            weights=weights,
            min_coverage=float(raw["data_confidence_min_coverage"]),
            min_score=float(raw["data_confidence_min_score"]),
            version=str(raw["version"]),
        )


@dataclass(frozen=True, slots=True)
class DataConfidenceAnalysis:
    score: float
    coverage: float
    rankable: bool
    components: dict[str, float]
    flags: tuple[str, ...]
    model_version: str


def analyze_data_confidence(
    inputs: DataConfidenceInputs,
    *,
    config: DataConfidenceConfig,
) -> DataConfidenceAnalysis:
    raw = {
        "completeness": inputs.completeness,
        "freshness": inputs.freshness,
        "official_source_share": inputs.official_source_share,
        "consistency": inputs.consistency,
        "point_in_time_lineage": inputs.point_in_time_lineage,
    }
    components: dict[str, float] = {}
    for name, value in raw.items():
        if value is None:
            continue
        numeric = float(value)
        if not 0.0 <= numeric <= 1.0:
            raise ValueError(f"{name} must be between 0 and 1")
        components[name] = numeric

    total_weight = sum(config.weights.values())
    available_weight = sum(config.weights[name] for name in components if name in config.weights)
    coverage = available_weight / total_weight if total_weight else 0.0
    normalized = (
        sum(components[name] * config.weights[name] for name in components if name in config.weights)
        / available_weight
        if available_weight
        else 0.0
    )
    score = normalized * 100.0
    flags: list[str] = []
    if coverage < config.min_coverage:
        flags.append("LOW_DATA_CONFIDENCE_COVERAGE")
    if score < config.min_score:
        flags.append("LOW_DATA_CONFIDENCE_SCORE")
    if inputs.point_in_time_lineage is not None and inputs.point_in_time_lineage < 0.80:
        flags.append("WEAK_POINT_IN_TIME_LINEAGE")
    return DataConfidenceAnalysis(
        score=score,
        coverage=coverage,
        rankable=coverage >= config.min_coverage and score >= config.min_score,
        components=components,
        flags=tuple(flags),
        model_version=config.version,
    )
