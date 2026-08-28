from __future__ import annotations

import hashlib
import re
import unicodedata
from datetime import UTC, datetime
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from ultimate_stock_analyzer.news.models import ArticleCluster, NewsArticle, SourceTier

_TRACKING_KEYS = {"fbclid", "gclid", "mc_cid", "mc_eid"}
_TIER_PRIORITY = {
    SourceTier.OFFICIAL: 0,
    SourceTier.SPECIALIZED: 1,
    SourceTier.OTHER: 2,
}


def canonical_url(url: str) -> str:
    parts = urlsplit(url.strip())
    query = [
        (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
        if not key.casefold().startswith("utm_") and key.casefold() not in _TRACKING_KEYS
    ]
    return urlunsplit((parts.scheme.casefold(), parts.netloc.casefold(), parts.path, urlencode(query), ""))


def normalized_headline_tokens(headline: str) -> frozenset[str]:
    folded = unicodedata.normalize("NFKD", headline.casefold())
    ascii_text = "".join(char for char in folded if not unicodedata.combining(char))
    return frozenset(token for token in re.findall(r"[a-z0-9]+", ascii_text) if len(token) > 2)


def headline_similarity(left: str, right: str) -> float:
    left_tokens = normalized_headline_tokens(left)
    right_tokens = normalized_headline_tokens(right)
    if not left_tokens or not right_tokens:
        return 0.0
    return len(left_tokens & right_tokens) / len(left_tokens | right_tokens)


def cluster_articles(
    articles: list[NewsArticle],
    *,
    similarity_threshold: float = 0.52,
    window_hours: float = 96.0,
) -> list[ArticleCluster]:
    if not 0.0 <= similarity_threshold <= 1.0:
        raise ValueError("similarity_threshold must be between 0 and 1")
    if window_hours <= 0:
        raise ValueError("window_hours must be positive")

    unique = _remove_exact_duplicates(articles)
    groups: list[list[NewsArticle]] = []
    ordered = sorted(unique, key=lambda article: _aware_timestamp(article.published_at))
    for article in ordered:
        matched: list[NewsArticle] | None = None
        for group in groups:
            representative = _representative(group)
            if article.ticker != representative.ticker:
                continue
            delta_hours = abs(
                (
                    _aware_timestamp(article.published_at)
                    - _aware_timestamp(representative.published_at)
                ).total_seconds()
            ) / 3600.0
            if delta_hours > window_hours:
                continue
            if headline_similarity(article.headline, representative.headline) >= similarity_threshold:
                matched = group
                break
        if matched is None:
            groups.append([article])
        else:
            matched.append(article)

    clusters: list[ArticleCluster] = []
    for group in groups:
        representative = _representative(group)
        article_ids = sorted(article.article_id for article in group)
        digest = hashlib.sha256("|".join(article_ids).encode("utf-8")).hexdigest()[:16]
        clusters.append(
            ArticleCluster(
                cluster_id=f"evt-{digest}",
                ticker=representative.ticker,
                representative=representative,
                articles=tuple(sorted(group, key=lambda article: article.article_id)),
            )
        )
    return clusters


def _remove_exact_duplicates(articles: list[NewsArticle]) -> list[NewsArticle]:
    chosen: dict[tuple[str, str], NewsArticle] = {}
    for article in articles:
        key = (article.ticker, canonical_url(article.source_url))
        current = chosen.get(key)
        if current is None or _representative_key(article) < _representative_key(current):
            chosen[key] = article
    return list(chosen.values())


def _representative(articles: list[NewsArticle]) -> NewsArticle:
    return min(articles, key=_representative_key)


def _representative_key(article: NewsArticle) -> tuple[int, int, str]:
    return (
        _TIER_PRIORITY[article.source_tier],
        -len(article.text),
        article.article_id,
    )


def _aware_timestamp(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
