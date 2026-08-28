from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from pathlib import Path
from typing import Any

import yaml


class EvidenceLevel(StrEnum):
    OFFICIAL = "OFFICIAL"
    SECONDARY = "SECONDARY"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True, slots=True)
class GovernanceConfig:
    version: str
    weights: dict[str, float]
    min_coverage: float
    min_official_evidence_share: float

    @classmethod
    def from_yaml(cls, path: str | Path) -> GovernanceConfig:
        with Path(path).open("r", encoding="utf-8") as file:
            raw: dict[str, Any] = yaml.safe_load(file)
        weights = {str(key): float(value) for key, value in raw["governance_weights"].items()}
        if any(weight <= 0 for weight in weights.values()):
            raise ValueError("governance weights must be positive")
        return cls(
            version=str(raw["version"]),
            weights=weights,
            min_coverage=float(raw["governance_min_coverage"]),
            min_official_evidence_share=float(raw["governance_min_official_share"]),
        )


@dataclass(frozen=True, slots=True)
class GovernanceEvidence:
    metric: str
    value: float | bool | str | None
    source: str
    reference_date: date | None
    collected_at: str | None = None
    evidence_level: EvidenceLevel = EvidenceLevel.OFFICIAL


@dataclass(frozen=True, slots=True)
class GovernanceAnalysis:
    score: float
    coverage: float
    official_evidence_share: float
    rankable: bool
    components: dict[str, float]
    flags: tuple[str, ...]
    evidence: tuple[GovernanceEvidence, ...]
    model_version: str


def analyze_governance(
    evidence: list[GovernanceEvidence],
    *,
    config: GovernanceConfig,
) -> GovernanceAnalysis:
    by_metric = {item.metric: item for item in evidence}
    components: dict[str, float] = {}

    _boolean_component(components, by_metric, "board_independence_adequate", 100.0, 25.0)
    _boolean_component(components, by_metric, "audit_committee_present", 100.0, 35.0)
    _boolean_component(components, by_metric, "fiscal_council_present", 90.0, 50.0)
    _boolean_component(components, by_metric, "related_party_policy_present", 100.0, 25.0)
    _boolean_component(components, by_metric, "compensation_disclosure_adequate", 100.0, 30.0)
    _boolean_component(components, by_metric, "tag_along_adequate", 100.0, 35.0)

    concentration = _number(by_metric.get("controller_voting_concentration"))
    if concentration is not None:
        components["controller_voting_concentration"] = _piecewise(
            concentration,
            ((0.20, 100.0), (0.35, 85.0), (0.50, 65.0), (0.70, 35.0), (0.90, 10.0), (1.0, 0.0)),
        )

    free_float = _number(by_metric.get("free_float"))
    if free_float is not None:
        components["free_float"] = _piecewise(
            free_float,
            ((0.10, 15.0), (0.20, 40.0), (0.25, 60.0), (0.35, 80.0), (0.50, 100.0)),
        )

    total_weight = sum(config.weights.values())
    available_weight = sum(config.weights[name] for name in components if name in config.weights)
    coverage = available_weight / total_weight if total_weight else 0.0
    score = (
        sum(components[name] * config.weights[name] for name in components if name in config.weights)
        / available_weight
        if available_weight
        else 50.0
    )

    official_share = (
        sum(item.evidence_level == EvidenceLevel.OFFICIAL for item in evidence) / len(evidence)
        if evidence
        else 0.0
    )
    flags: list[str] = []
    if coverage < config.min_coverage:
        flags.append("LOW_GOVERNANCE_DATA_COVERAGE")
    if official_share < config.min_official_evidence_share:
        flags.append("LOW_OFFICIAL_EVIDENCE_SHARE")
    if concentration is not None and concentration >= 0.80:
        flags.append("HIGH_CONTROL_CONCENTRATION")
    related_party = by_metric.get("related_party_policy_present")
    if related_party is not None and related_party.value is False:
        flags.append("RELATED_PARTY_POLICY_GAP")

    rankable = (
        coverage >= config.min_coverage
        and official_share >= config.min_official_evidence_share
    )
    return GovernanceAnalysis(
        score=max(0.0, min(100.0, score)),
        coverage=max(0.0, min(1.0, coverage)),
        official_evidence_share=max(0.0, min(1.0, official_share)),
        rankable=rankable,
        components=components,
        flags=tuple(flags),
        evidence=tuple(evidence),
        model_version=config.version,
    )


def _boolean_component(
    output: dict[str, float],
    evidence: dict[str, GovernanceEvidence],
    metric: str,
    true_score: float,
    false_score: float,
) -> None:
    item = evidence.get(metric)
    if item is None or not isinstance(item.value, bool):
        return
    output[metric] = true_score if item.value else false_score


def _number(item: GovernanceEvidence | None) -> float | None:
    if item is None or isinstance(item.value, bool) or not isinstance(item.value, (int, float)):
        return None
    return float(item.value)


def _piecewise(value: float, anchors: tuple[tuple[float, float], ...]) -> float:
    if value <= anchors[0][0]:
        return anchors[0][1]
    if value >= anchors[-1][0]:
        return anchors[-1][1]
    for index in range(1, len(anchors)):
        left_x, left_y = anchors[index - 1]
        right_x, right_y = anchors[index]
        if left_x <= value <= right_x:
            fraction = (value - left_x) / (right_x - left_x)
            return left_y + fraction * (right_y - left_y)
    return 50.0
