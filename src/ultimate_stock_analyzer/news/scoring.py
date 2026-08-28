from __future__ import annotations

from datetime import datetime, timezone

from ultimate_stock_analyzer.domain.models import NewsSignal


def aggregate_news_score(
    signals: list[NewsSignal],
    as_of: datetime | None = None,
    half_life_days: float = 30.0,
) -> float:
    """Map relevant evidence into a conservative 0..100 score with temporal decay.

    Baseline 50 is neutral. Irrelevant events do not move the score. Duplicate detection/event
    clustering belongs upstream; this function assumes one signal per material event.
    """
    if half_life_days <= 0:
        raise ValueError("half_life_days must be positive")
    if as_of is None:
        as_of = datetime.now(timezone.utc)
    if as_of.tzinfo is None:
        as_of = as_of.replace(tzinfo=timezone.utc)

    numerator = 0.0
    denominator = 0.0
    for signal in signals:
        if not signal.relevant:
            continue
        age_days = 0.0
        if signal.published_at is not None:
            published = signal.published_at
            if published.tzinfo is None:
                published = published.replace(tzinfo=timezone.utc)
            age_days = max(0.0, (as_of - published).total_seconds() / 86400.0)
        decay = 0.5 ** (age_days / half_life_days)
        weight = (signal.severity / 5.0) * signal.confidence * decay
        numerator += signal.impact * weight
        denominator += weight

    if denominator == 0:
        return 50.0
    normalized_impact = max(-1.0, min(1.0, numerator / denominator))
    return 50.0 + 50.0 * normalized_impact
