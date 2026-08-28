from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import yaml

from ultimate_stock_analyzer.news.models import SourceTier


@dataclass(frozen=True, slots=True)
class SourceRegistry:
    official_domains: frozenset[str]
    specialized_domains: frozenset[str]

    @classmethod
    def from_yaml(cls, path: str | Path) -> SourceRegistry:
        with Path(path).open("r", encoding="utf-8") as file:
            raw: dict[str, Any] = yaml.safe_load(file)
        return cls(
            official_domains=frozenset(_normalize_domain(value) for value in raw["official_domains"]),
            specialized_domains=frozenset(
                _normalize_domain(value) for value in raw["specialized_domains"]
            ),
        )

    def classify_url(self, url: str, *, official_override: bool = False) -> SourceTier:
        if official_override:
            return SourceTier.OFFICIAL
        hostname = _normalize_domain(urlsplit(url).hostname or "")
        if _matches_domain(hostname, self.official_domains):
            return SourceTier.OFFICIAL
        if _matches_domain(hostname, self.specialized_domains):
            return SourceTier.SPECIALIZED
        return SourceTier.OTHER


def _matches_domain(hostname: str, domains: frozenset[str]) -> bool:
    return any(hostname == domain or hostname.endswith(f".{domain}") for domain in domains)


def _normalize_domain(value: str) -> str:
    return value.strip().casefold().removeprefix("www.")
