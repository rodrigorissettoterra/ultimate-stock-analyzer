from __future__ import annotations

from collections.abc import Mapping


def percentile_rank(values: Mapping[str, float | None], higher_is_better: bool = True) -> dict[str, float | None]:
    """Return 0..100 percentile-like ranks. Ties receive the same average rank."""
    valid = {k: float(v) for k, v in values.items() if v is not None}
    result: dict[str, float | None] = {k: None for k in values}
    if not valid:
        return result
    if len(valid) == 1:
        only = next(iter(valid))
        result[only] = 50.0
        return result

    ordered_values = sorted(set(valid.values()))
    rank_map: dict[float, float] = {}
    n = len(ordered_values)
    for i, value in enumerate(ordered_values):
        pct = 100.0 * i / (n - 1)
        rank_map[value] = pct if higher_is_better else 100.0 - pct

    for key, value in valid.items():
        result[key] = rank_map[value]
    return result


def target_score(value: float | None, target: float, tolerance: float) -> float | None:
    if value is None:
        return None
    if tolerance <= 0:
        raise ValueError("tolerance must be positive")
    distance = abs(value - target)
    return max(0.0, 100.0 * (1.0 - distance / tolerance))
