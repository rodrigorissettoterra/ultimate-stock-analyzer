from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from ultimate_stock_analyzer.scoring.normalization import (
    peer_adjusted_percentile_rank,
    target_score,
)


@dataclass(frozen=True, slots=True)
class StructuralMetricRule:
    name: str
    category: str
    weight: float
    direction: str
    sectors: tuple[str, ...] = ("*",)
    target: float | None = None
    tolerance: float | None = None
    min_peer_count: int | None = None


@dataclass(frozen=True, slots=True)
class StructuralCategoryScore:
    name: str
    score: float
    coverage: float
    confidence: float
    contributions: dict[str, float] = field(default_factory=dict)
    peer_reliability: dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class StructuralScoreResult:
    ticker: str
    sector: str
    structural_score: float
    data_coverage: float
    confidence: float
    rankable: bool
    categories: dict[str, StructuralCategoryScore]
    peer_group: str = ""
    model_family: str = ""
    model_id: str = ""
    selection_reason: str = ""
    flags: tuple[str, ...] = ()
    model_version: str = ""


class StructuralScoringConfig:
    def __init__(self, raw: dict[str, Any]) -> None:
        self.version = str(raw["version"])
        self.model_family = str(raw.get("model_family", "general_corporate_v1"))
        self.peer_group_field = str(raw.get("peer_group_field", "sector"))
        self.default_min_peer_count = int(raw.get("default_min_peer_count", 8))
        self.min_coverage_for_ranking = float(raw.get("min_coverage_for_ranking", 0.65))
        self.min_confidence_for_ranking = float(raw.get("min_confidence_for_ranking", 0.55))
        self.category_weights: dict[str, float] = {
            str(name): float(weight)
            for name, weight in raw["category_weights"].items()
        }
        self.metric_rules = tuple(
            StructuralMetricRule(
                name=str(rule["name"]),
                category=str(rule["category"]),
                weight=float(rule["weight"]),
                direction=str(rule["direction"]),
                sectors=tuple(str(item) for item in rule.get("sectors", ["*"])),
                target=(
                    float(rule["target"])
                    if rule.get("target") is not None
                    else None
                ),
                tolerance=(
                    float(rule["tolerance"])
                    if rule.get("tolerance") is not None
                    else None
                ),
                min_peer_count=(
                    int(rule["min_peer_count"])
                    if rule.get("min_peer_count") is not None
                    else None
                ),
            )
            for rule in raw["metrics"]
        )
        unknown_categories = {
            rule.category for rule in self.metric_rules
        } - self.category_weights.keys()
        if unknown_categories:
            raise ValueError(
                "metric rules reference undefined categories: "
                + ", ".join(sorted(unknown_categories))
            )

    @classmethod
    def from_yaml(cls, path: str | Path) -> StructuralScoringConfig:
        with Path(path).open("r", encoding="utf-8") as file:
            return cls(yaml.safe_load(file))


class StructuralScoringEngine:
    """Deterministic long-horizon company-quality scoring.

    Price-dependent valuation, dividend yield, news, securities lending and entry-timing
    signals are deliberately excluded from this engine.
    """

    def __init__(self, config: StructuralScoringConfig) -> None:
        self.config = config

    def score_universe(self, rows: list[dict[str, Any]]) -> list[StructuralScoreResult]:
        by_peer_group: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in rows:
            peer_group = str(
                row.get(self.config.peer_group_field)
                or row.get("sector")
                or "UNCLASSIFIED"
            )
            by_peer_group[peer_group].append(row)

        metric_scores: dict[str, dict[str, float | None]] = defaultdict(dict)
        metric_reliability: dict[str, dict[str, float]] = defaultdict(dict)

        for peer_rows in by_peer_group.values():
            tickers = [str(row["ticker"]) for row in peer_rows]
            for rule in self.config.metric_rules:
                applicable_rows = [
                    (ticker, peer_rows[index])
                    for index, ticker in enumerate(tickers)
                    if _applies(rule, str(peer_rows[index]["sector"]))
                ]
                if not applicable_rows:
                    continue
                values = {
                    ticker: row.get(rule.name)
                    for ticker, row in applicable_rows
                }
                if rule.direction in {"higher", "lower"}:
                    scores, reliability = peer_adjusted_percentile_rank(
                        values,
                        higher_is_better=rule.direction == "higher",
                        min_peer_count=(
                            rule.min_peer_count or self.config.default_min_peer_count
                        ),
                    )
                    for ticker, score in scores.items():
                        metric_scores[ticker][rule.name] = score
                        if score is not None:
                            metric_reliability[ticker][rule.name] = reliability
                elif rule.direction == "target":
                    if rule.target is None or rule.tolerance is None:
                        raise ValueError(
                            f"target rule {rule.name} requires target and tolerance"
                        )
                    for ticker, value in values.items():
                        score = target_score(value, rule.target, rule.tolerance)
                        metric_scores[ticker][rule.name] = score
                        if score is not None:
                            metric_reliability[ticker][rule.name] = 1.0
                else:
                    raise ValueError(f"unsupported direction: {rule.direction}")

        results = [
            self._score_row(row, metric_scores, metric_reliability)
            for row in rows
        ]
        return sorted(
            results,
            key=lambda result: (
                result.rankable,
                result.structural_score,
                result.confidence,
            ),
            reverse=True,
        )

    def rank_universe(self, rows: list[dict[str, Any]]) -> list[StructuralScoreResult]:
        return [result for result in self.score_universe(rows) if result.rankable]

    def _score_row(
        self,
        row: dict[str, Any],
        metric_scores: dict[str, dict[str, float | None]],
        metric_reliability: dict[str, dict[str, float]],
    ) -> StructuralScoreResult:
        ticker = str(row["ticker"])
        sector = str(row["sector"])
        peer_group = str(
            row.get(self.config.peer_group_field)
            or row.get("sector")
            or "UNCLASSIFIED"
        )
        categories: dict[str, StructuralCategoryScore] = {}

        for category in self.config.category_weights:
            applicable = [
                rule
                for rule in self.config.metric_rules
                if rule.category == category and _applies(rule, sector)
            ]
            total_weight = sum(rule.weight for rule in applicable)
            available: list[tuple[StructuralMetricRule, float, float]] = []
            for rule in applicable:
                score = metric_scores[ticker].get(rule.name)
                if score is None:
                    continue
                reliability = metric_reliability[ticker].get(rule.name, 0.0)
                available.append((rule, score, reliability))

            available_weight = sum(rule.weight for rule, _, _ in available)
            if total_weight <= 0 or available_weight <= 0:
                continue
            category_score = sum(
                score * rule.weight for rule, score, _ in available
            ) / available_weight
            coverage = available_weight / total_weight
            reliability = sum(
                peer_confidence * rule.weight
                for rule, _, peer_confidence in available
            ) / available_weight
            categories[category] = StructuralCategoryScore(
                name=category,
                score=category_score,
                coverage=coverage,
                confidence=coverage * reliability,
                contributions={rule.name: score for rule, score, _ in available},
                peer_reliability={
                    rule.name: peer_confidence
                    for rule, _, peer_confidence in available
                },
            )

        total_category_weight = sum(self.config.category_weights.values())
        evidenced_weight = sum(
            self.config.category_weights[name] * category.coverage
            for name, category in categories.items()
        )
        data_coverage = (
            evidenced_weight / total_category_weight
            if total_category_weight > 0
            else 0.0
        )

        effective_weight = evidenced_weight
        if effective_weight > 0:
            structural_score = sum(
                category.score
                * self.config.category_weights[name]
                * category.coverage
                for name, category in categories.items()
            ) / effective_weight
            confidence = sum(
                category.confidence * self.config.category_weights[name]
                for name, category in categories.items()
            ) / total_category_weight
        else:
            structural_score = 50.0
            confidence = 0.0

        flags: list[str] = []
        if data_coverage < self.config.min_coverage_for_ranking:
            flags.append("LOW_STRUCTURAL_DATA_COVERAGE")
        if confidence < self.config.min_confidence_for_ranking:
            flags.append("LOW_STRUCTURAL_CONFIDENCE")
        if any(
            reliability < 1.0
            for category in categories.values()
            for reliability in category.peer_reliability.values()
        ):
            flags.append("SMALL_PEER_GROUP_SHRINKAGE")
        if not categories:
            flags.append("NO_STRUCTURAL_DATA")

        rankable = (
            data_coverage >= self.config.min_coverage_for_ranking
            and confidence >= self.config.min_confidence_for_ranking
        )
        return StructuralScoreResult(
            ticker=ticker,
            sector=sector,
            structural_score=max(0.0, min(100.0, structural_score)),
            data_coverage=max(0.0, min(1.0, data_coverage)),
            confidence=max(0.0, min(1.0, confidence)),
            rankable=rankable,
            categories=categories,
            peer_group=peer_group,
            model_family=self.config.model_family,
            flags=tuple(flags),
            model_version=self.config.version,
        )


def _applies(rule: StructuralMetricRule, sector: str) -> bool:
    return "*" in rule.sectors or sector in rule.sectors
