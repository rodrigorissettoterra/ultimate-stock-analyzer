from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from ultimate_stock_analyzer.domain.models import NewsSignal


class SourceTier(StrEnum):
    OFFICIAL = "OFFICIAL"
    SPECIALIZED = "SPECIALIZED"
    OTHER = "OTHER"


@dataclass(frozen=True, slots=True)
class NewsArticle:
    article_id: str
    ticker: str
    headline: str
    text: str
    source_name: str
    source_url: str
    published_at: datetime
    source_tier: SourceTier = SourceTier.OTHER


@dataclass(frozen=True, slots=True)
class ArticleCluster:
    cluster_id: str
    ticker: str
    representative: NewsArticle
    articles: tuple[NewsArticle, ...]


@dataclass(frozen=True, slots=True)
class ClassifiedNewsEvent:
    cluster_id: str
    ticker: str
    representative: NewsArticle
    signal: NewsSignal
    article_ids: tuple[str, ...]
