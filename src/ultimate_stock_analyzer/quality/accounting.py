from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum
from itertools import pairwise
from pathlib import Path
from typing import Any

import yaml


class AccountingQualityStatus(StrEnum):
    STRONG = "STRONG"
    ACCEPTABLE = "ACCEPTABLE"
    WEAK = "WEAK"
    HIGH_RISK = "HIGH_RISK"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


@dataclass(frozen=True, slots=True)
class AccountingQualityConfig:
    version: str
    weights: dict[str, float]
    min_coverage: float

    @classmethod
    def from_yaml(cls, path: str | Path) -> AccountingQualityConfig:
        with Path(path).open("r", encoding="utf-8") as file:
            raw: dict[str, Any] = yaml.safe_load(file)
        weights = {str(key): float(value) for key, value in raw["accounting_weights"].items()}
        if any(weight <= 0 for weight in weights.values()):
            raise ValueError("accounting weights must be positive")
        return cls(
            version=str(raw["version"]),
            weights=weights,
            min_coverage=float(raw["accounting_min_coverage"]),
        )


@dataclass(frozen=True, slots=True)
class AccountingInputs:
    net_income: float | None = None
    operating_cash_flow: float | None = None
    free_cash_flow: float | None = None
    total_assets_begin: float | None = None
    total_assets_end: float | None = None
    revenue: float | None = None
    receivables_begin: float | None = None
    receivables_end: float | None = None
    inventories_begin: float | None = None
    inventories_end: float | None = None
    nonrecurring_income: float | None = None


@dataclass(frozen=True, slots=True)
class AccountingQualityAnalysis:
    score: float
    coverage: float
    rankable: bool
    status: AccountingQualityStatus
    metrics: dict[str, float | None]
    components: dict[str, float]
    flags: tuple[str, ...]
    model_version: str


def analyze_accounting_quality(
    inputs: AccountingInputs,
    *,
    config: AccountingQualityConfig,
) -> AccountingQualityAnalysis:
    metrics = accounting_quality_metrics(inputs)
    components: dict[str, float] = {}

    conversion = metrics["cfo_to_net_income"]
    if conversion is not None:
        components["cash_conversion"] = _piecewise(
            conversion,
            ((0.0, 0.0), (0.5, 25.0), (0.8, 60.0), (1.0, 85.0), (1.2, 100.0), (2.0, 90.0), (3.0, 60.0)),
        )

    accruals = metrics["accrual_ratio"]
    if accruals is not None:
        components["accruals"] = _piecewise(
            abs(accruals),
            ((0.0, 100.0), (0.03, 90.0), (0.07, 70.0), (0.12, 45.0), (0.20, 15.0), (0.30, 0.0)),
        )

    fcf_conversion = metrics["fcf_to_net_income"]
    if fcf_conversion is not None:
        components["fcf_conversion"] = _piecewise(
            fcf_conversion,
            ((-1.0, 0.0), (0.0, 15.0), (0.5, 50.0), (0.8, 75.0), (1.0, 90.0), (1.5, 100.0), (2.5, 80.0)),
        )

    receivables_ratio = metrics["receivables_change_to_revenue"]
    if receivables_ratio is not None:
        components["receivables_quality"] = _piecewise(
            receivables_ratio,
            ((-0.10, 100.0), (0.0, 90.0), (0.03, 75.0), (0.07, 55.0), (0.12, 20.0), (0.20, 0.0)),
        )

    inventory_ratio = metrics["inventory_change_to_revenue"]
    if inventory_ratio is not None:
        components["inventory_quality"] = _piecewise(
            inventory_ratio,
            ((-0.10, 100.0), (0.0, 90.0), (0.03, 75.0), (0.07, 55.0), (0.12, 20.0), (0.20, 0.0)),
        )

    nonrecurring_ratio = metrics["nonrecurring_income_to_net_income"]
    if nonrecurring_ratio is not None:
        components["nonrecurring_quality"] = _piecewise(
            abs(nonrecurring_ratio),
            ((0.0, 100.0), (0.05, 90.0), (0.15, 70.0), (0.30, 40.0), (0.50, 10.0), (0.80, 0.0)),
        )

    total_weight = sum(config.weights.values())
    available_weight = sum(config.weights[name] for name in components if name in config.weights)
    score = (
        sum(components[name] * config.weights[name] for name in components if name in config.weights)
        / available_weight
        if available_weight
        else 50.0
    )
    coverage = available_weight / total_weight if total_weight else 0.0
    rankable = coverage >= config.min_coverage
    flags: list[str] = []
    if coverage < config.min_coverage:
        flags.append("LOW_ACCOUNTING_DATA_COVERAGE")
    if accruals is not None and abs(accruals) > 0.15:
        flags.append("HIGH_ACCRUALS")
    if conversion is not None and conversion < 0.7:
        flags.append("WEAK_CASH_CONVERSION")
    if nonrecurring_ratio is not None and abs(nonrecurring_ratio) > 0.30:
        flags.append("HIGH_NONRECURRING_INCOME")

    status = _status(score) if rankable else AccountingQualityStatus.INSUFFICIENT_DATA
    return AccountingQualityAnalysis(
        score=max(0.0, min(100.0, score)),
        coverage=max(0.0, min(1.0, coverage)),
        rankable=rankable,
        status=status,
        metrics=metrics,
        components=components,
        flags=tuple(flags),
        model_version=config.version,
    )


def accounting_quality_metrics(inputs: AccountingInputs) -> dict[str, float | None]:
    average_assets = _average(inputs.total_assets_begin, inputs.total_assets_end)
    accrual_numerator = (
        None
        if inputs.net_income is None or inputs.operating_cash_flow is None
        else inputs.net_income - inputs.operating_cash_flow
    )
    return {
        "cfo_to_net_income": _safe_div(inputs.operating_cash_flow, inputs.net_income),
        "fcf_to_net_income": _safe_div(inputs.free_cash_flow, inputs.net_income),
        "accrual_ratio": _safe_div(accrual_numerator, average_assets),
        "receivables_change_to_revenue": _balance_change_to_revenue(
            inputs.receivables_begin,
            inputs.receivables_end,
            inputs.revenue,
        ),
        "inventory_change_to_revenue": _balance_change_to_revenue(
            inputs.inventories_begin,
            inputs.inventories_end,
            inputs.revenue,
        ),
        "nonrecurring_income_to_net_income": _safe_div(inputs.nonrecurring_income, inputs.net_income),
    }


def _balance_change_to_revenue(begin: float | None, end: float | None, revenue: float | None) -> float | None:
    if begin is None or end is None or revenue is None or revenue <= 0:
        return None
    return (end - begin) / revenue


def _safe_div(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or denominator is None or denominator == 0:
        return None
    value = numerator / denominator
    return value if math.isfinite(value) else None


def _average(left: float | None, right: float | None) -> float | None:
    values = [value for value in (left, right) if value is not None]
    return sum(values) / len(values) if values else None


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


def _status(score: float) -> AccountingQualityStatus:
    if score >= 80:
        return AccountingQualityStatus.STRONG
    if score >= 60:
        return AccountingQualityStatus.ACCEPTABLE
    if score >= 35:
        return AccountingQualityStatus.WEAK
    return AccountingQualityStatus.HIGH_RISK
