from datetime import UTC, datetime

from ultimate_stock_analyzer.domain.models import NewsSignal
from ultimate_stock_analyzer.news.models import NewsArticle, SourceTier
from ultimate_stock_analyzer.news.pipeline import classify_news_articles


class FakeClassifier:
    def __init__(self) -> None:
        self.calls = 0

    def classify(
        self,
        ticker: str,
        headline: str,
        text: str,
        source_url: str | None = None,
        source_name: str | None = None,
    ) -> NewsSignal:
        self.calls += 1
        return NewsSignal(
            ticker=ticker,
            relevant=True,
            event_type="GUIDANCE",
            impact=0.6,
            severity=4,
            confidence=0.9,
            rationale=f"Synthetic classification from {source_name}",
            source_url=source_url,
        )


def test_pipeline_calls_llm_once_for_duplicate_event_cluster() -> None:
    now = datetime(2026, 8, 1, tzinfo=UTC)
    articles = [
        NewsArticle(
            article_id="a",
            ticker="TEST3",
            headline="Empresa eleva guidance 2026",
            text="Synthetic media report",
            source_name="Media",
            source_url="https://x.test/a",
            published_at=now,
            source_tier=SourceTier.SPECIALIZED,
        ),
        NewsArticle(
            article_id="b",
            ticker="TEST3",
            headline="Empresa eleva o guidance para 2026",
            text="Synthetic official disclosure",
            source_name="RI",
            source_url="https://ri.test/b",
            published_at=now,
            source_tier=SourceTier.OFFICIAL,
        ),
    ]
    classifier = FakeClassifier()
    result = classify_news_articles(articles, classifier)
    assert result.clustered_events == 1
    assert result.llm_calls == 1
    assert classifier.calls == 1
    assert result.events[0].representative.source_tier == SourceTier.OFFICIAL
