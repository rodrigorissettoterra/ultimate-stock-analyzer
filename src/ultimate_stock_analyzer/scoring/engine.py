from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from ultimate_stock_analyzer.domain.models import (
    AnalysisResult,
    CategoryScore,
    Recommendation,
    RedFlag,
)
from ultimate_stock_analyzer.scoring.normalization import percentile_rank, target_score


@dataclass(frozen=True, slots=True)
class MetricRule:
    name: str
    category: str
    weight: float
    direction: str
    sectors: tuple[str, ...] = ("*",)
    target: float | None = None
    tolerance: float | None = None


class ScoringConfig:
    def __init__(self, raw: dict[str, Any]) -> None:
        self.version = str(raw["version"])
        self.metric_rules = tuple(MetricRule(**r) for r in raw["metrics"])
        self.quality_category_weights: dict[str, float] = raw["quality_category_weights"]
        self.investment_weights: dict[str, float] = raw["investment_weights"]
        self.final_weights: dict[str, float] = raw["final_weights"]
        self.thresholds: dict[str, float] = raw["recommendation_thresholds"]
        self.min_confidence = float(raw.get("min_confidence_for_positive_label", 0.70))

    @classmethod
    def from_yaml(cls, path: str | Path) -> "ScoringConfig":
        with open(path, "r", encoding="utf-8") as f:
            return cls(yaml.safe_load(f))


def _weighted_average(items: list[tuple[float, float]]) -> tuple[float, float]:
    """Return score and coverage where weights are already scoped to the category."""
    if not items:
        return 0.0, 0.0
    total_weight = sum(weight for _, weight in items)
    if total_weight <= 0:
        return 0.0, 0.0
    score = sum(value * weight for value, weight in items) / total_weight
    return score, min(1.0, total_weight)


def _recommendation(score: float, entry: float, confidence: float, blocked: bool, thresholds: dict[str, float], min_confidence: float) -> Recommendation:
    if blocked:
        return Recommendation.BLOCKED
    if confidence < min_confidence:
        return Recommendation.WATCH
    if score >= thresholds["very_attractive"] and entry >= thresholds["entry_support"]:
        return Recommendation.VERY_ATTRACTIVE
    if score >= thresholds["attractive"] and entry >= thresholds["entry_support"]:
        return Recommendation.ATTRACTIVE
    if score < thresholds["avoid"]:
        return Recommendation.AVOID
    if entry < thresholds["wait_entry"]:
        return Recommendation.WAIT
    return Recommendation.WATCH


class ScoringEngine:
    """Cross-sectional, sector-aware and deterministic scoring engine.

    Input rows are dictionaries containing `ticker`, `sector` and precomputed numeric metrics.
    The LLM is deliberately not involved in this class.
    """

    def __init__(self, config: ScoringConfig) -> None:
        self.config = config

    def score_universe(
        self,
        rows: list[dict[str, Any]],
        red_flags: dict[str, list[RedFlag]] | None = None,
    ) -> list[AnalysisResult]:
        red_flags = red_flags or {}
        by_sector: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in rows:
            by_sector[str(row["sector"])].append(row)

        metric_scores: dict[str, dict[str, float | None]] = defaultdict(dict)

        for sector, sector_rows in by_sector.items():
            tickers = [str(r["ticker"]) for r in sector_rows]
            for rule in self.config.metric_rules:
                if "*" not in rule.sectors and sector not in rule.sectors:
                    continue
                values = {ticker: sector_rows[i].get(rule.name) for i, ticker in enumerate(tickers)}
                if rule.direction == "higher":
                    scores = percentile_rank(values, higher_is_better=True)
                elif rule.direction == "lower":
                    scores = percentile_rank(values, higher_is_better=False)
                elif rule.direction == "target":
                    if rule.target is None or rule.tolerance is None:
                        raise ValueError(f"target rule {rule.name} missing target/tolerance")
                    scores = {k: target_score(v, rule.target, rule.tolerance) for k, v in values.items()}
                else:
                    raise ValueError(f"unsupported direction: {rule.direction}")
                for ticker, score in scores.items():
                    metric_scores[ticker][rule.name] = score

        results: list[AnalysisResult] = []
        for row in rows:
            ticker = str(row["ticker"])
            sector = str(row["sector"])
            categories: dict[str, CategoryScore] = {}

            grouped: dict[str, list[tuple[str, float, float]]] = defaultdict(list)
            for rule in self.config.metric_rules:
                if "*" not in rule.sectors and sector not in rule.sectors:
                    continue
                score = metric_scores[ticker].get(rule.name)
                if score is not None:
                    grouped[rule.category].append((rule.name, score, rule.weight))

            for category, contributions in grouped.items():
                max_weight = sum(
                    r.weight
                    for r in self.config.metric_rules
                    if r.category == category and ("*" in r.sectors or sector in r.sectors)
                )
                weighted_sum = sum(score * weight for _, score, weight in contributions)
                actual_weight = sum(weight for _, _, weight in contributions)
                score = weighted_sum / actual_weight if actual_weight else 0.0
                coverage = actual_weight / max_weight if max_weight else 0.0
                categories[category] = CategoryScore(
                    name=category,
                    score=score,
                    coverage=coverage,
                    contributions={name: value for name, value, _ in contributions},
                )

            quality_parts: list[tuple[float, float]] = []
            for category, weight in self.config.quality_category_weights.items():
                if category in categories:
                    quality_parts.append((categories[category].score, weight))
            quality_score, _ = _weighted_average(quality_parts)

            def cat(name: str, default: float = 50.0) -> float:
                return categories[name].score if name in categories else float(row.get(f"{name}_score", default))

            valuation = cat("valuation")
            news = float(row.get("news_score", cat("news")))
            rental = float(row.get("rental_score", cat("rental")))
            macro = float(row.get("macro_score", cat("macro")))
            liquidity = float(row.get("liquidity_score", cat("liquidity")))
            risk = float(row.get("risk_score", cat("risk")))
            short_pressure = float(row.get("short_pressure_score", 50.0))
            entry = float(row.get("entry_score", cat("entry")))

            iw = self.config.investment_weights
            positive = (
                quality_score * iw["quality"]
                + valuation * iw["valuation"]
                + news * iw["news"]
                + rental * iw["rental"]
                + macro * iw["macro"]
                + liquidity * iw["liquidity"]
            )
            penalties = risk * iw.get("risk_penalty", 0.0) + short_pressure * iw.get("short_pressure_penalty", 0.0)
            investment = max(0.0, min(100.0, positive - penalties))

            fw = self.config.final_weights
            final_score = max(
                0.0,
                min(
                    100.0,
                    investment * fw["investment"]
                    + entry * fw["entry"]
                    + news * fw["news"]
                    + rental * fw["rental"],
                ),
            )

            all_coverages = [c.coverage for c in categories.values()]
            coverage_confidence = sum(all_coverages) / len(all_coverages) if all_coverages else 0.0
            source_confidence = float(row.get("source_confidence", 1.0))
            freshness_confidence = float(row.get("freshness_confidence", 1.0))
            conflict_confidence = float(row.get("conflict_confidence", 1.0))
            confidence = max(
                0.0,
                min(1.0, 0.55 * coverage_confidence + 0.20 * source_confidence + 0.15 * freshness_confidence + 0.10 * conflict_confidence),
            )

            flags = red_flags.get(ticker, [])
            blocked = any(flag.blocking for flag in flags)
            rec = _recommendation(final_score, entry, confidence, blocked, self.config.thresholds, self.config.min_confidence)

            results.append(
                AnalysisResult(
                    ticker=ticker,
                    company_name=row.get("company_name"),
                    sector=sector,
                    current_price=row.get("current_price"),
                    dy_ttm=row.get("dy_ttm"),
                    lending_rate_annual=row.get("lending_rate_annual"),
                    lending_utilization=row.get("lending_utilization"),
                    categories=categories,
                    company_quality_score=quality_score,
                    investment_score=investment,
                    entry_score=entry,
                    final_score=final_score,
                    data_confidence=confidence * 100.0,
                    recommendation=rec,
                    red_flags=flags,
                    metadata={"model_version": self.config.version},
                )
            )
        return sorted(results, key=lambda r: r.final_score, reverse=True)
