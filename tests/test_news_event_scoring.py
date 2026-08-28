from datetime import UTC, datetime

from ultimate_stock_analyzer.domain.models import NewsSignal
from ultimate_stock_analyzer.news.models import ClassifiedNewsEvent, NewsArticle, SourceTier
from ultimate_stock_analyzer.news.scoring import aggregate_event_score


def _event(event_id: str, impact: float, tier: SourceTier) -> ClassifiedNewsEvent:
    published = datetime(2026, 8, 1, tzinfo=UTC)
    article = NewsArticle(
        article_id=event_id,
        ticker="TEST3",
        headline="Synthetic material event",
        text="Synthetic test only",
        source_name=tier.value,
        source_url=f"https://example.test/{event_id}",
        published_at=published,
        source_tier=tier,
    )
    signal = NewsSignal(
        ticker="TEST3",
        relevant=True,
        event_type="GUIDANCE",
        impact=impact,
        severity=4,
        confidence=0.9,
        rationale="Synthetic",
        source_url=article.source_url,
        published_at=published,
    )
    return ClassifiedNewsEvent(event_id, "TEST3", article, signal, (event_id,))


def test_positive_and_negative_material_events_move_score_in_expected_direction() -> None:
    as_of = datetime(2026, 8, 2, tzinfo=UTC)
    positive = aggregate_event_score([_event("p", 0.8, SourceTier.OFFICIAL)], as_of=as_of)
    negative = aggregate_event_score([_event("n", -0.8, SourceTier.OFFICIAL)], as_of=as_of)
    assert positive.score > 50
    assert negative.score < 50
    assert positive.confidence > 0.8
