from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from ultimate_stock_analyzer.domain.models import NewsSignal
from ultimate_stock_analyzer.news.models import ClassifiedNewsEvent, SourceTier

_SOURCE_WEIGHT = {
    SourceTier.OFFICIAL: 1.00,
    SourceTier.SPECIALIZED: 0.85,
    SourceTier.OTHER: 0.65,
}
_DEFAULT_HALF_LIVES = {
    "BANKRUPTCY": 180.0,
    "DEFAULT": 180.0,
    "FRAUD": 180.0,
    "ACCOUNTING": 120.0,
    "REGULATORY": 90.0,
    "M&A": 90.0,
    "MANAGEMENT": 60.0,
    "GUIDANCE": 45.0,
    "EARNINGS": 45.0,
    "DIVIDEND": 30.0,
}


@dataclass(frozen=True, slots=True)
class NewsScoreResult:
    score: float
    confidence: float
    total_events: int
    relevant_events: int
    positive_events: int
    negative_events: int
    flags: tuple[str, ...]


def aggregate_event_score(
    events: list[ClassifiedNewsEvent] | tuple[ClassifiedNewsEvent, ...],
    *,
    as_of: datetime | None = None,
    default_half_life_days: float = 30.0,
) -> NewsScoreResult:
    if default_half_life_days <= 0:
        raise ValueError("default_half_life_days must be positive")
    as_of = _aware(as_of or datetime.now(UTC))
    numerator = 0.0
    denominator = 0.0
    confidence_weight = 0.0
    relevant = 0
    positive = 0
    negative = 0
    official_relevant = 0

    for event in events:
        signal = event.signal
        if not signal.relevant:
            continue
        relevant += 1
        positive += signal.impact > 0
        negative += signal.impact < 0
        if event.representative.source_tier == SourceTier.OFFICIAL:
            official_relevant += 1
        age_days = max(
            0.0,
            (as_of - _aware(signal.published_at or event.representative.published_at)).total_seconds()
            / 86400.0,
        )
        half_life = _event_half_life(signal.event_type, default_half_life_days)
        decay = 0.5 ** (age_days / half_life)
        source_weight = _SOURCE_WEIGHT[event.representative.source_tier]
        weight = (signal.severity / 5.0) * signal.confidence * source_weight * decay
        numerator += signal.impact * weight
        denominator += weight
        confidence_weight += signal.confidence * source_weight

    if denominator == 0:
        score = 50.0
    else:
        normalized = max(-1.0, min(1.0, numerator / denominator))
        score = 50.0 + 50.0 * normalized
    confidence = confidence_weight / relevant if relevant else 0.0
    flags: list[str] = []
    if not events:
        flags.append("NO_NEWS_EVENTS")
    if relevant and official_relevant == 0:
        flags.append("NO_OFFICIAL_RELEVANT_EVENT_SOURCE")
    if relevant and confidence < 0.45:
        flags.append("LOW_NEWS_CONFIDENCE")
    return NewsScoreResult(
        score=max(0.0, min(100.0, score)),
        confidence=max(0.0, min(1.0, confidence)),
        total_events=len(events),
        relevant_events=relevant,
        positive_events=positive,
        negative_events=negative,
        flags=tuple(flags),
    )


def aggregate_news_score(
    signals: list[NewsSignal],
    as_of: datetime | None = None,
    half_life_days: float = 30.0,
) -> float:
    """Backward-compatible signal-only score; M12 event scoring is preferred."""
    if half_life_days <= 0:
        raise ValueError("half_life_days must be positive")
    as_of = _aware(as_of or datetime.now(UTC))
    numerator = 0.0
    denominator = 0.0
    for signal in signals:
        if not signal.relevant:
            continue
        published = _aware(signal.published_at) if signal.published_at is not None else as_of
        age_days = max(0.0, (as_of - published).total_seconds() / 86400.0)
        decay = 0.5 ** (age_days / half_life_days)
        weight = (signal.severity / 5.0) * signal.confidence * decay
        numerator += signal.impact * weight
        denominator += weight
    if denominator == 0:
        return 50.0
    normalized_impact = max(-1.0, min(1.0, numerator / denominator))
    return 50.0 + 50.0 * normalized_impact


def _event_half_life(event_type: str, default: float) -> float:
    normalized = event_type.upper().strip()
    for key, value in _DEFAULT_HALF_LIVES.items():
        if key in normalized:
            return value
    return default


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
