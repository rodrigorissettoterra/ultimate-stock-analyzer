from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from ultimate_stock_analyzer.domain.models import NewsSignal
from ultimate_stock_analyzer.news.dedup import cluster_articles
from ultimate_stock_analyzer.news.models import ClassifiedNewsEvent, NewsArticle


class NewsClassifier(Protocol):
    def classify(
        self,
        ticker: str,
        headline: str,
        text: str,
        source_url: str | None = None,
        source_name: str | None = None,
    ) -> NewsSignal: ...


@dataclass(frozen=True, slots=True)
class NewsPipelineResult:
    events: tuple[ClassifiedNewsEvent, ...]
    input_articles: int
    clustered_events: int
    llm_calls: int


def classify_news_articles(
    articles: list[NewsArticle],
    classifier: NewsClassifier,
    *,
    similarity_threshold: float = 0.52,
    window_hours: float = 96.0,
) -> NewsPipelineResult:
    clusters = cluster_articles(
        articles,
        similarity_threshold=similarity_threshold,
        window_hours=window_hours,
    )
    events: list[ClassifiedNewsEvent] = []
    for cluster in clusters:
        article = cluster.representative
        signal = classifier.classify(
            article.ticker,
            article.headline,
            article.text,
            article.source_url,
            article.source_name,
        )
        signal = signal.model_copy(update={"published_at": article.published_at})
        events.append(
            ClassifiedNewsEvent(
                cluster_id=cluster.cluster_id,
                ticker=article.ticker,
                representative=article,
                signal=signal,
                article_ids=tuple(item.article_id for item in cluster.articles),
            )
        )
    return NewsPipelineResult(
        events=tuple(events),
        input_articles=len(articles),
        clustered_events=len(clusters),
        llm_calls=len(clusters),
    )
