from __future__ import annotations


def utilization(loaned_quantity: float | None, free_float_shares: float | None) -> float | None:
    if loaned_quantity is None or free_float_shares is None or free_float_shares <= 0:
        return None
    return max(0.0, loaned_quantity / free_float_shares)


def rental_opportunity_score(rate_annual: float | None, utilization_ratio: float | None) -> float:
    """Backward-compatible transparent heuristic; prefer M11 engine for production ranking."""
    components: list[tuple[float, float]] = []
    if rate_annual is not None:
        components.append((min(1.0, max(0.0, rate_annual / 0.12)), 0.70))
    if utilization_ratio is not None:
        components.append((min(1.0, max(0.0, utilization_ratio / 0.20)), 0.30))
    if not components:
        return 50.0
    weight = sum(item_weight for _, item_weight in components)
    return 100.0 * sum(value * item_weight for value, item_weight in components) / weight


def short_pressure_score(
    utilization_ratio: float | None,
    utilization_change_20d: float | None = None,
    lending_rate_annual: float | None = None,
) -> float:
    """Backward-compatible heuristic; missing values are omitted, never silently set to zero."""
    components: list[tuple[float, float]] = []
    if utilization_ratio is not None:
        components.append((min(1.0, max(0.0, utilization_ratio / 0.25)), 0.55))
    if utilization_change_20d is not None:
        components.append((min(1.0, max(0.0, utilization_change_20d / 0.10)), 0.25))
    if lending_rate_annual is not None:
        components.append((min(1.0, max(0.0, lending_rate_annual / 0.15)), 0.20))
    if not components:
        return 50.0
    weight = sum(item_weight for _, item_weight in components)
    return 100.0 * sum(value * item_weight for value, item_weight in components) / weight
