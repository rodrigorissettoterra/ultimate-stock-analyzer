from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import httpx


@dataclass(slots=True)
class BCBSeriesCollector:
    timeout_seconds: float = 30.0

    def build_url(self, series_code: int, start: date | None = None, end: date | None = None) -> str:
        base = f"https://api.bcb.gov.br/dados/serie/bcdata.sgs.{series_code}/dados?formato=json"
        params: list[str] = []
        if start:
            params.append(f"dataInicial={start.strftime('%d/%m/%Y')}")
        if end:
            params.append(f"dataFinal={end.strftime('%d/%m/%Y')}")
        return base + ("&" + "&".join(params) if params else "")

    def fetch(self, series_code: int, start: date | None = None, end: date | None = None) -> list[dict[str, str]]:
        with httpx.Client(timeout=self.timeout_seconds, follow_redirects=True) as client:
            response = client.get(self.build_url(series_code, start, end))
            response.raise_for_status()
            data = response.json()
        if not isinstance(data, list):
            raise TypeError("unexpected BCB response")
        return data
