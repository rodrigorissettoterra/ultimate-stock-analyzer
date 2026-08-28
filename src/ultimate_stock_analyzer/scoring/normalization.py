from __future__ import annotations

from collections.abc import Mapping
from itertools import groupby


def percentile_rank(
    values: Mapping[str, float | None],
    higher_is_better: bool = True,
) -> dict[str, float | None]:
    """Return 0..100 empirical percentile ranks with average ranks for ties."""
    valid = {key: float(value) for key, value in values.items() if value is not None}
    result: dict[str, float | None] = {key: None for key in values}
    if not valid:
        return result
    if len(valid) == 1:
        only = next(iter(valid))
        result[only] = 50.0
        return result

    ordered = sorted(valid.items(), key=lambda item: item[1])
    denominator = len(ordered) - 1
    position = 0
    for _, group_iterator in groupby(ordered, key=lambda item: item[1]):
        group = list(group_iterator)
        first_position = position
        last_position = position + len(group) - 1
        average_position = (first_position + last_position) / 2.0
        percentile = 100.0 * average_position / denominator
        score = percentile if higher_is_better else 100.0 - percentile
        for key, _ in group:
            result[key] = score
        position = last_position + 1
    return result


def peer_reliability(peer_count: int, min_peer_count: int = 8) -> float:
    """Return 0..1 confidence in a cross-sectional peer comparison."""
    if min_peer_count <= 1:
        return 1.0
    if peer_count <= 1:
        return 0.0
    return min(1.0, (peer_count - 1) / (min_peer_count - 1))


def peer_adjusted_percentile_rank(
    values: Mapping[str, float | None],
    *,
    higher_is_better: bool = True,
    min_peer_count: int = 8,
) -> tuple[dict[str, float | None], float]:
    """Shrink percentile scores toward neutral when peer samples are small."""
    raw = percentile_rank(values, higher_is_better=higher_is_better)
    peer_count = sum(value is not None for value in values.values())
    reliability = peer_reliability(peer_count, min_peer_count=min_peer_count)
    adjusted = {
        key: None if score is None else 50.0 + reliability * (score - 50.0)
        for key, score in raw.items()
    }
    return adjusted, reliability


def target_score(value: float | None, target: float, tolerance: float) -> float | None:
    if value is None:
        return None
    if tolerance <= 0:
        raise ValueError("tolerance must be positive")
    distance = abs(value - target)
    return max(0.0, 100.0 * (1.0 - distance / tolerance))
