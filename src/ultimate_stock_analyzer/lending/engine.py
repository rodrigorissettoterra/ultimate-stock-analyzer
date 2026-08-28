from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from itertools import pairwise
from pathlib import Path
from typing import Any

import yaml

from ultimate_stock_analyzer.lending.models import (
    LendingOpenPositionRecord,
    LoanBalanceRecord,
)


class LendingStatus(StrEnum):
    ATTRACTIVE = "ATTRACTIVE"
    MODERATE = "MODERATE"
    LOW = "LOW"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


@dataclass(frozen=True, slots=True)
class LendingConfig:
    version: str
    opportunity_weights: dict[str, float]
    pressure_weights: dict[str, float]
    min_coverage: float
    min_confidence: float
    history_target: int

    @classmethod
    def from_yaml(cls, path: str | Path) -> LendingConfig:
        with Path(path).open("r", encoding="utf-8") as file:
            raw: dict[str, Any] = yaml.safe_load(file)
        opportunity = {
            str(key): float(value) for key, value in raw["rental_opportunity_weights"].items()
        }
        pressure = {
            str(key): float(value) for key, value in raw["short_pressure_weights"].items()
        }
        if any(weight <= 0 for weight in (*opportunity.values(), *pressure.values())):
            raise ValueError("lending weights must be positive")
        return cls(
            version=str(raw["version"]),
            opportunity_weights=opportunity,
            pressure_weights=pressure,
            min_coverage=float(raw["min_coverage"]),
            min_confidence=float(raw["min_confidence"]),
            history_target=int(raw["open_position_history_target"]),
        )


@dataclass(frozen=True, slots=True)
class LendingAnalysis:
    ticker: str
    report_date: str
    rental_opportunity_score: float
    short_pressure_risk: float
    net_lending_score: float
    opportunity_coverage: float
    pressure_coverage: float
    confidence: float
    rankable: bool
    status: LendingStatus
    metrics: dict[str, float | None]
    opportunity_components: dict[str, float]
    pressure_components: dict[str, float]
    flags: tuple[str, ...]
    model_version: str


def analyze_lending(
    flows: list[LoanBalanceRecord],
    open_positions: list[LendingOpenPositionRecord],
    *,
    free_float_shares: float | None,
    config: LendingConfig,
) -> LendingAnalysis:
    tickers = {record.ticker for record in (*flows, *open_positions)}
    if not tickers:
        raise ValueError("lending data is required")
    if len(tickers) != 1:
        raise ValueError("all lending records must belong to one ticker")
    ticker = next(iter(tickers))

    latest_date = max(record.report_date for record in (*flows, *open_positions))
    latest_flows = [record for record in flows if record.report_date == latest_date]
    latest_open = _open_position_for_date(open_positions, latest_date)
    flow = _aggregate_daily_flow(latest_flows) if latest_flows else None

    free_float = _positive(free_float_shares)
    open_quantity = latest_open.balance_quantity if latest_open is not None else None
    utilization = _ratio(open_quantity, free_float)
    daily_flow_ratio = _ratio(flow.shares_day if flow else None, free_float)
    utilization_change = _utilization_change(open_positions, free_float, periods=20)
    donor_rate = flow.donor_avg_rate if flow else None
    taker_rate = flow.taker_avg_rate if flow else None

    opportunity_components: dict[str, float] = {}
    if donor_rate is not None:
        opportunity_components["donor_rate"] = _piecewise(
            donor_rate,
            ((0.0, 0.0), (0.005, 20.0), (0.02, 45.0), (0.05, 70.0), (0.10, 90.0), (0.20, 100.0)),
        )
    if utilization is not None:
        opportunity_components["utilization"] = _piecewise(
            utilization,
            ((0.0, 0.0), (0.02, 20.0), (0.05, 45.0), (0.10, 70.0), (0.20, 90.0), (0.30, 100.0)),
        )
    if daily_flow_ratio is not None:
        opportunity_components["daily_flow"] = _piecewise(
            daily_flow_ratio,
            ((0.0, 0.0), (0.0005, 20.0), (0.002, 50.0), (0.005, 75.0), (0.01, 90.0), (0.02, 100.0)),
        )

    pressure_components: dict[str, float] = {}
    if utilization is not None:
        pressure_components["utilization"] = _piecewise(
            utilization,
            ((0.0, 0.0), (0.02, 15.0), (0.05, 35.0), (0.10, 60.0), (0.20, 85.0), (0.30, 100.0)),
        )
    if utilization_change is not None:
        pressure_components["utilization_momentum"] = _piecewise(
            utilization_change,
            ((-0.05, 0.0), (0.0, 35.0), (0.02, 60.0), (0.05, 80.0), (0.10, 100.0)),
        )
    if taker_rate is not None:
        pressure_components["taker_rate"] = _piecewise(
            taker_rate,
            ((0.0, 0.0), (0.005, 15.0), (0.02, 40.0), (0.05, 65.0), (0.10, 85.0), (0.20, 100.0)),
        )

    opportunity_score, opportunity_coverage = _weighted_score(
        opportunity_components,
        config.opportunity_weights,
    )
    pressure_score, pressure_coverage = _weighted_score(
        pressure_components,
        config.pressure_weights,
    )

    history_dates = {record.report_date for record in open_positions}
    history_confidence = min(1.0, len(history_dates) / max(config.history_target, 1))
    overall_coverage = min(opportunity_coverage, pressure_coverage)
    confidence = overall_coverage * (0.60 + 0.40 * history_confidence)

    flags: list[str] = []
    if latest_open is None:
        flags.append("OPEN_POSITION_UNAVAILABLE")
    if free_float is None:
        flags.append("FREE_FLOAT_UNAVAILABLE")
    if flow is None:
        flags.append("DAILY_LENDING_FLOW_UNAVAILABLE")
    elif flow.shares_day <= 0:
        flags.append("NO_NEW_LENDING_ACTIVITY")
        confidence *= 0.85
    if utilization_change is None:
        flags.append("UTILIZATION_MOMENTUM_UNAVAILABLE")
    if overall_coverage < config.min_coverage:
        flags.append("LOW_LENDING_DATA_COVERAGE")
    if confidence < config.min_confidence:
        flags.append("LOW_LENDING_CONFIDENCE")

    rankable = overall_coverage >= config.min_coverage and confidence >= config.min_confidence
    net_score = 0.75 * opportunity_score + 0.25 * (100.0 - pressure_score)
    status = _status(opportunity_score) if rankable else LendingStatus.INSUFFICIENT_DATA
    return LendingAnalysis(
        ticker=ticker,
        report_date=latest_date.isoformat(),
        rental_opportunity_score=opportunity_score,
        short_pressure_risk=pressure_score,
        net_lending_score=max(0.0, min(100.0, net_score)),
        opportunity_coverage=opportunity_coverage,
        pressure_coverage=pressure_coverage,
        confidence=max(0.0, min(1.0, confidence)),
        rankable=rankable,
        status=status,
        metrics={
            "donor_avg_rate_annual": donor_rate,
            "taker_avg_rate_annual": taker_rate,
            "open_quantity": open_quantity,
            "open_value": latest_open.balance_value if latest_open else None,
            "loan_utilization": utilization,
            "utilization_change_20_observations": utilization_change,
            "daily_contracts": float(flow.contracts_day) if flow else None,
            "daily_loaned_shares": flow.shares_day if flow else None,
            "daily_lending_value": flow.value_day if flow else None,
            "daily_flow_to_free_float": daily_flow_ratio,
        },
        opportunity_components=opportunity_components,
        pressure_components=pressure_components,
        flags=tuple(flags),
        model_version=config.version,
    )


def _aggregate_daily_flow(records: list[LoanBalanceRecord]) -> LoanBalanceRecord:
    if not records:
        raise ValueError("records are required")
    ticker = records[0].ticker
    report_date = records[0].report_date
    if any(record.ticker != ticker or record.report_date != report_date for record in records):
        raise ValueError("daily lending flow aggregation requires one ticker and date")
    shares = sum(max(record.shares_day, 0.0) for record in records)
    return LoanBalanceRecord(
        report_date=report_date,
        ticker=ticker,
        isin=next((record.isin for record in records if record.isin), None),
        asset=next((record.asset for record in records if record.asset), None),
        market="AGGREGATED",
        contracts_day=sum(max(record.contracts_day, 0) for record in records),
        shares_day=shares,
        value_day=sum(max(record.value_day, 0.0) for record in records),
        donor_min_rate=_minimum(record.donor_min_rate for record in records),
        donor_avg_rate=_weighted_rate(records, "donor_avg_rate"),
        donor_max_rate=_maximum(record.donor_max_rate for record in records),
        taker_min_rate=_minimum(record.taker_min_rate for record in records),
        taker_avg_rate=_weighted_rate(records, "taker_avg_rate"),
        taker_max_rate=_maximum(record.taker_max_rate for record in records),
        source="B3_LOAN_BALANCE_AGGREGATED",
    )


def _open_position_for_date(
    records: list[LendingOpenPositionRecord],
    report_date: date,
) -> LendingOpenPositionRecord | None:
    same_date = [record for record in records if record.report_date == report_date]
    if not same_date:
        return None
    totals = [record for record in same_date if (record.market or "").casefold() == "total"]
    if totals:
        return max(totals, key=lambda record: record.balance_quantity)
    if len(same_date) == 1:
        return same_date[0]
    quantity = sum(max(record.balance_quantity, 0.0) for record in same_date)
    values = [record.balance_value for record in same_date if record.balance_value is not None]
    return LendingOpenPositionRecord(
        report_date=report_date,
        ticker=same_date[0].ticker,
        isin=next((record.isin for record in same_date if record.isin), None),
        asset=next((record.asset for record in same_date if record.asset), None),
        balance_quantity=quantity,
        trade_average_price=None,
        price_factor=None,
        balance_value=sum(values) if values else None,
        market="AGGREGATED",
        source="B3_LENDING_OPEN_POSITION_AGGREGATED",
    )


def _daily_open_quantities(records: list[LendingOpenPositionRecord]) -> list[tuple[date, float]]:
    dates = sorted({record.report_date for record in records})
    output: list[tuple[date, float]] = []
    for report_date in dates:
        aggregated = _open_position_for_date(records, report_date)
        if aggregated is not None:
            output.append((report_date, aggregated.balance_quantity))
    return output


def _utilization_change(
    records: list[LendingOpenPositionRecord],
    free_float: float | None,
    *,
    periods: int,
) -> float | None:
    if free_float is None or periods <= 0:
        return None
    ordered = _daily_open_quantities(records)
    if len(ordered) <= periods:
        return None
    earlier = ordered[-periods - 1][1] / free_float
    latest = ordered[-1][1] / free_float
    return latest - earlier


def _weighted_rate(records: list[LoanBalanceRecord], attribute: str) -> float | None:
    weighted_sum = 0.0
    weight_sum = 0.0
    fallback: list[float] = []
    for record in records:
        value = getattr(record, attribute)
        if value is None:
            continue
        fallback.append(float(value))
        if record.shares_day > 0:
            weighted_sum += float(value) * record.shares_day
            weight_sum += record.shares_day
    if weight_sum > 0:
        return weighted_sum / weight_sum
    return sum(fallback) / len(fallback) if fallback else None


def _weighted_score(components: dict[str, float], weights: dict[str, float]) -> tuple[float, float]:
    total_weight = sum(weights.values())
    available_weight = sum(weights[name] for name in components if name in weights)
    if available_weight <= 0 or total_weight <= 0:
        return 50.0, 0.0
    score = sum(components[name] * weights[name] for name in components if name in weights) / available_weight
    return max(0.0, min(100.0, score)), available_weight / total_weight


def _ratio(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or denominator is None or denominator <= 0:
        return None
    return max(0.0, numerator / denominator)


def _positive(value: float | None) -> float | None:
    return float(value) if value is not None and value > 0 else None


def _minimum(values: Iterable[float | None]) -> float | None:
    present = [float(value) for value in values if value is not None]
    return min(present) if present else None


def _maximum(values: Iterable[float | None]) -> float | None:
    present = [float(value) for value in values if value is not None]
    return max(present) if present else None


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


def _status(score: float) -> LendingStatus:
    if score >= 75:
        return LendingStatus.ATTRACTIVE
    if score >= 45:
        return LendingStatus.MODERATE
    return LendingStatus.LOW
