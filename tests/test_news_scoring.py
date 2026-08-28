from datetime import datetime, timezone

from ultimate_stock_analyzer.domain.models import NewsSignal
from ultimate_stock_analyzer.news.scoring import aggregate_news_score


def test_relevant_negative_news_reduces_score() -> None:
    now = datetime(2026, 8, 28, tzinfo=timezone.utc)
    signals = [
        NewsSignal(ticker="TEST3", relevant=True, event_type="default", impact=-1.0, severity=5, confidence=1.0, rationale="test", published_at=now),
        NewsSignal(ticker="TEST3", relevant=False, event_type="noise", impact=1.0, severity=5, confidence=1.0, rationale="ignore", published_at=now),
    ]
    assert aggregate_news_score(signals, as_of=now) == 0.0
