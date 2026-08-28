from __future__ import annotations


def data_confidence(
    coverage: float,
    source_quality: float,
    freshness: float,
    consistency: float,
) -> float:
    """Return confidence on a 0..100 scale from four independently auditable inputs."""
    vals = [coverage, source_quality, freshness, consistency]
    vals = [max(0.0, min(1.0, float(v))) for v in vals]
    score = 0.50 * vals[0] + 0.20 * vals[1] + 0.15 * vals[2] + 0.15 * vals[3]
    return score * 100.0
