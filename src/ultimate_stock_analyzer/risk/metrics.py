from __future__ import annotations

import math
from collections.abc import Sequence


def downside_deviation(returns: Sequence[float], target: float = 0.0, annualization: int = 252) -> float | None:
    vals = [float(r) for r in returns if math.isfinite(float(r))]
    if not vals:
        return None
    downs = [min(0.0, r - target) ** 2 for r in vals]
    return math.sqrt(sum(downs) / len(downs)) * math.sqrt(annualization)


def sortino_ratio(returns: Sequence[float], risk_free_daily: float = 0.0, annualization: int = 252) -> float | None:
    vals = [float(r) for r in returns if math.isfinite(float(r))]
    if not vals:
        return None
    excess = [r - risk_free_daily for r in vals]
    dd = downside_deviation(excess, 0.0, annualization)
    if dd in (None, 0.0):
        return None
    annualized_mean = (sum(excess) / len(excess)) * annualization
    return annualized_mean / dd


def historical_var(returns: Sequence[float], confidence: float = 0.95) -> float | None:
    vals = sorted(float(r) for r in returns if math.isfinite(float(r)))
    if not vals or not 0 < confidence < 1:
        return None
    idx = max(0, min(len(vals) - 1, int((1 - confidence) * len(vals))))
    return -vals[idx]


def historical_cvar(returns: Sequence[float], confidence: float = 0.95) -> float | None:
    vals = sorted(float(r) for r in returns if math.isfinite(float(r)))
    if not vals or not 0 < confidence < 1:
        return None
    cutoff = max(1, int((1 - confidence) * len(vals)))
    tail = vals[:cutoff]
    return -sum(tail) / len(tail)
