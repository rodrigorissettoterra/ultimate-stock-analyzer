from __future__ import annotations


def utilization(loaned_quantity: float | None, free_float_shares: float | None) -> float | None:
    if loaned_quantity is None or free_float_shares is None or free_float_shares <= 0:
        return None
    return max(0.0, loaned_quantity / free_float_shares)


def rental_opportunity_score(rate_annual: float | None, utilization_ratio: float | None) -> float:
    """Transparent 0..100 income-opportunity heuristic; not a buy signal."""
    rate_component = min(1.0, max(0.0, (rate_annual or 0.0) / 0.12))
    util_component = min(1.0, max(0.0, (utilization_ratio or 0.0) / 0.20))
    return 100.0 * (0.70 * rate_component + 0.30 * util_component)


def short_pressure_score(
    utilization_ratio: float | None,
    utilization_change_20d: float | None = None,
    lending_rate_annual: float | None = None,
) -> float:
    util = min(1.0, max(0.0, (utilization_ratio or 0.0) / 0.25))
    change = min(1.0, max(0.0, (utilization_change_20d or 0.0) / 0.10))
    rate = min(1.0, max(0.0, (lending_rate_annual or 0.0) / 0.15))
    return 100.0 * (0.55 * util + 0.25 * change + 0.20 * rate)
