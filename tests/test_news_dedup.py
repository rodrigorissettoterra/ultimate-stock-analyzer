from datetime import UTC, datetime, timedelta

from ultimate_stock_analyzer.news.dedup import canonical_url, cluster_articles
from ultimate_stock_analyzer.news.models import NewsArticle, SourceTier


def _article(
    article_id: str,
    headline: str,
    source_url: str,
    *,
    tier: SourceTier,
    hours: int = 0,
) -> NewsArticle:
    return NewsArticle(
        article_id=article_id,
        ticker="TEST3",
        headline=headline,
        text=f"Synthetic evidence for {headline}",
        source_name=tier.value,
        source_url=source_url,
        published_at=datetime(2026, 8, 1, tzinfo=UTC) + timedelta(hours=hours),
        source_tier=tier,
    )


def test_tracking_parameters_do_not_create_duplicate_url() -> None:
    assert canonical_url("https://example.com/a?utm_source=x&id=1") == canonical_url(
        "https://example.com/a?id=1&utm_medium=y"
    )


def test_similar_event_prefers_official_representative() -> None:
    articles = [
        _article(
            "media-1",
            "TEST anuncia novo guidance para 2026",
            "https://news.example/test-guidance",
            tier=SourceTier.SPECIALIZED,
        ),
        _article(
            "official-1",
            "TEST anuncia novo guidance 2026",
            "https://ri.example/guidance",
            tier=SourceTier.OFFICIAL,
            hours=1,
        ),
    ]
    clusters = cluster_articles(articles)
    assert len(clusters) == 1
    assert clusters[0].representative.article_id == "official-1"
