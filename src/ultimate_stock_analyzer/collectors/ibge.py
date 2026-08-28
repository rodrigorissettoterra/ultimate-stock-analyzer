from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import quote

import httpx

_SIDRA_BASE = "https://apisidra.ibge.gov.br/values"


@dataclass(slots=True)
class SIDRACollector:
    """Minimal free-first client for official IBGE SIDRA API paths.

    SIDRA queries are path-based and table-specific. The collector deliberately keeps query
    construction explicit rather than hiding table dimensions behind brittle assumptions.
    """

    timeout_seconds: float = 30.0

    def build_url(self, query_path: str) -> str:
        cleaned = query_path.strip().strip("/")
        if not cleaned or "://" in cleaned or ".." in cleaned:
            raise ValueError("invalid SIDRA query path")
        segments = [quote(segment, safe=",-@") for segment in cleaned.split("/")]
        return f"{_SIDRA_BASE}/{'/'.join(segments)}"

    def fetch(self, query_path: str) -> list[dict[str, str]]:
        with httpx.Client(timeout=self.timeout_seconds, follow_redirects=True) as client:
            response = client.get(self.build_url(query_path))
            response.raise_for_status()
            payload = response.json()
        if not isinstance(payload, list):
            raise TypeError("unexpected SIDRA response")
        return [
            {str(key): "" if value is None else str(value) for key, value in row.items()}
            for row in payload
            if isinstance(row, dict)
        ]
