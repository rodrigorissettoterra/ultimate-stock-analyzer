from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

import yaml

from ultimate_stock_analyzer.quality.data_confidence import DataConfidenceAnalysis


class DecisionStatus(StrEnum):
    VERY_ATTRACTIVE = "VERY_ATTRACTIVE"
    ATTRACTIVE = "ATTRACTIVE"
    WATCH = "WATCH"
    WAIT = "WAIT"
    AVOID = "AVOID"
    BLOCKED = "BLOCKED"
    INCONCLUSIVE = "INCONCLUSIVE"


@dataclass(frozen=True, slots=True)
class ScoreInput:
    score: float | None
    confidence: float = 1.0
    rankable: bool = True

    def __post_init__(self) -> None:
        if self.score is not None and not 0.0 <= self.score <= 100.0:
            raise ValueError("score must be between 0 and 100")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between 0 and 1")


@dataclass(frozen=True, slots=True)
class IntegratedConfig:
    version: str
    quality_weights: dict[str, float]
    investment_weights: dict[str, float]
    min_quality_coverage: float
    min_investment_coverage: float
    min_component_confidence: float
    actionability_investment_weight: float
    thresholds: dict[str, float]

    @classmethod
    def from_yaml(cls, path: str | Path) -> IntegratedConfig:
        with Path(path).open("r", encoding="utf-8") as file:
            raw: dict[str, Any] = yaml.safe_load(file)
        quality = {str(key): float(value) for key, value in raw["company_quality_weights"].items()}
        investment = {
            str(key): float(value) for key, value in raw["investment_attractiveness_weights"].items()
        }
        if any(weight <= 0 for weight in (*quality.values(), *investment.values())):
            raise ValueError("integrated score weights must be positive")
        return cls(
            version=str(raw["version"]),
            quality_weights=quality,
            investment_weights=investment,
            min_quality_coverage=float(raw["min_company_quality_coverage"]),
            min_investment_coverage=float(raw["min_investment_coverage"]),
            min_component_confidence=float(raw["min_component_confidence"]),
            actionability_investment_weight=float(raw["actionability_investment_weight"]),
            thresholds={str(key): float(value) for key, value in raw["decision_thresholds"].items()},
        )


@dataclass(frozen=True, slots=True)
class IntegratedInputs:
    structural: ScoreInput
    accounting_quality: ScoreInput
    governance: ScoreInput
    audit_risk_score: ScoreInput
    valuation: ScoreInput
    news: ScoreInput
    macro: ScoreInput
    risk_safety: ScoreInput
    liquidity: ScoreInput
    lending_net: ScoreInput
    entry: ScoreInput
    data_confidence: DataConfidenceAnalysis
    audit_blocked: bool = False
    red_flag_blocked: bool = False


@dataclass(frozen=True, slots=True)
class IntegratedDecision:
    company_quality_score: float
    investment_attractiveness_score: float
    entry_timing_score: float
    ranking_score: float
    actionability_score: float
    company_quality_coverage: float
    investment_coverage: float
    component_confidence: float
    data_confidence_score: float
    rankable: bool
    status: DecisionStatus
    quality_contributions: dict[str, float]
    investment_contributions: dict[str, float]
    flags: tuple[str, ...]
    model_version: str


def analyze_integrated_decision(
    inputs: IntegratedInputs,
    *,
    config: IntegratedConfig,
) -> IntegratedDecision:
    quality_components = {
        "structural": inputs.structural,
        "accounting_quality": inputs.accounting_quality,
        "governance": inputs.governance,
        "audit_safety": ScoreInput(
            None if inputs.audit_risk_score.score is None else 100.0 - inputs.audit_risk_score.score,
            confidence=inputs.audit_risk_score.confidence,
            rankable=inputs.audit_risk_score.rankable,
        ),
    }
    quality, quality_coverage, quality_confidence, quality_contrib = _aggregate(
        quality_components,
        config.quality_weights,
        config.min_component_confidence,
    )

    investment_components = {
        "company_quality": ScoreInput(quality, confidence=quality_confidence, rankable=quality_coverage >= config.min_quality_coverage),
        "valuation": inputs.valuation,
        "news": inputs.news,
        "macro": inputs.macro,
        "risk_safety": inputs.risk_safety,
        "liquidity": inputs.liquidity,
        "lending_net": inputs.lending_net,
    }
    investment, investment_coverage, investment_confidence, investment_contrib = _aggregate(
        investment_components,
        config.investment_weights,
        config.min_component_confidence,
    )

    entry = inputs.entry.score if inputs.entry.score is not None else 50.0
    ranking_score = investment
    investment_weight = config.actionability_investment_weight
    if not 0.0 <= investment_weight <= 1.0:
        raise ValueError("actionability investment weight must be between 0 and 1")
    actionability = investment * investment_weight + entry * (1.0 - investment_weight)
    component_confidence = min(quality_confidence, investment_confidence, inputs.entry.confidence)

    flags: list[str] = []
    if quality_coverage < config.min_quality_coverage:
        flags.append("LOW_COMPANY_QUALITY_COVERAGE")
    if investment_coverage < config.min_investment_coverage:
        flags.append("LOW_INVESTMENT_COVERAGE")
    if not inputs.data_confidence.rankable:
        flags.extend(inputs.data_confidence.flags)
    if not inputs.structural.rankable or inputs.structural.score is None:
        flags.append("STRUCTURAL_SCORE_REQUIRED")
    if not inputs.valuation.rankable or inputs.valuation.score is None:
        flags.append("VALUATION_SCORE_REQUIRED")
    if not inputs.entry.rankable or inputs.entry.score is None:
        flags.append("ENTRY_SCORE_REQUIRED")

    blocked = inputs.audit_blocked or inputs.red_flag_blocked
    rankable = (
        not blocked
        and quality_coverage >= config.min_quality_coverage
        and investment_coverage >= config.min_investment_coverage
        and inputs.data_confidence.rankable
        and inputs.structural.rankable
        and inputs.structural.score is not None
        and inputs.valuation.rankable
        and inputs.valuation.score is not None
        and inputs.entry.rankable
        and inputs.entry.score is not None
    )
    status = _decision_status(
        quality,
        investment,
        entry,
        rankable=rankable,
        blocked=blocked,
        thresholds=config.thresholds,
    )
    return IntegratedDecision(
        company_quality_score=quality,
        investment_attractiveness_score=investment,
        entry_timing_score=entry,
        ranking_score=ranking_score,
        actionability_score=actionability,
        company_quality_coverage=quality_coverage,
        investment_coverage=investment_coverage,
        component_confidence=component_confidence,
        data_confidence_score=inputs.data_confidence.score,
        rankable=rankable,
        status=status,
        quality_contributions=quality_contrib,
        investment_contributions=investment_contrib,
        flags=tuple(dict.fromkeys(flags)),
        model_version=config.version,
    )


def _aggregate(
    components: dict[str, ScoreInput],
    weights: dict[str, float],
    min_confidence: float,
) -> tuple[float, float, float, dict[str, float]]:
    total_weight = sum(weights.values())
    available: list[tuple[str, ScoreInput, float]] = []
    for name, weight in weights.items():
        component = components.get(name)
        if (
            component is None
            or component.score is None
            or not component.rankable
            or component.confidence < min_confidence
        ):
            continue
        available.append((name, component, weight))
    available_weight = sum(weight for _, _, weight in available)
    if available_weight <= 0 or total_weight <= 0:
        return 50.0, 0.0, 0.0, {}
    score = sum(float(component.score) * weight for _, component, weight in available) / available_weight
    confidence = sum(component.confidence * weight for _, component, weight in available) / available_weight
    contributions = {
        name: float(component.score) * weight / available_weight
        for name, component, weight in available
    }
    return score, available_weight / total_weight, confidence, contributions


def _decision_status(
    quality: float,
    investment: float,
    entry: float,
    *,
    rankable: bool,
    blocked: bool,
    thresholds: dict[str, float],
) -> DecisionStatus:
    if blocked:
        return DecisionStatus.BLOCKED
    if not rankable:
        return DecisionStatus.INCONCLUSIVE
    if quality < thresholds["avoid_quality"] or investment < thresholds["avoid_investment"]:
        return DecisionStatus.AVOID
    if (
        quality >= thresholds["very_attractive_quality"]
        and investment >= thresholds["very_attractive_investment"]
        and entry >= thresholds["very_attractive_entry"]
    ):
        return DecisionStatus.VERY_ATTRACTIVE
    if (
        quality >= thresholds["attractive_quality"]
        and investment >= thresholds["attractive_investment"]
        and entry >= thresholds["attractive_entry"]
    ):
        return DecisionStatus.ATTRACTIVE
    if investment >= thresholds["wait_investment"] and entry < thresholds["wait_entry"]:
        return DecisionStatus.WAIT
    return DecisionStatus.WATCH
