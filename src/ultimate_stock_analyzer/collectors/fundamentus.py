from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from io import StringIO
from time import monotonic, sleep

import httpx
import pandas as pd

from ultimate_stock_analyzer.dividends.regularity import DividendPayment

DEFAULT_USER_AGENT = "ultimate-stock-analyzer/0.1"


def get_snapshot() -> pd.DataFrame:
    """Optional convenience adapter; never treated as the project's source of truth."""
    try:
        import fundamentus  # type: ignore[import-not-found]
    except ImportError as exc:
        raise RuntimeError("Install optional package `fundamentus` to use this adapter") from exc
    frame = fundamentus.get_resultado()
    if not isinstance(frame, pd.DataFrame):
        raise TypeError("fundamentus.get_resultado() did not return a DataFrame")
    return frame.copy()


def get_company_details(tickers: str | list[str]) -> pd.DataFrame:
    try:
        import fundamentus  # type: ignore[import-not-found]
    except ImportError as exc:
        raise RuntimeError("Install optional package `fundamentus` to use this adapter") from exc
    frame = fundamentus.get_papel(tickers)
    if not isinstance(frame, pd.DataFrame):
        raise TypeError("fundamentus.get_papel() did not return a DataFrame")
    return frame.copy()


@dataclass(slots=True)
class FundamentusDividendCollector:
    """Conservative public-page fallback for historical dividend/JCP observations.

    This collector does not bypass access controls, does not redistribute source data and should
    be rate-limited. B3/CVM remain preferred authoritative sources where equivalent structured
    data is available.
    """

    user_agent: str = DEFAULT_USER_AGENT
    timeout_seconds: float = 30.0
    min_request_interval_seconds: float = 1.0
    _last_request_monotonic: float = 0.0

    def build_url(self, ticker: str) -> str:
        safe = "".join(ch for ch in ticker.upper() if ch.isalnum())
        if not safe:
            raise ValueError("invalid ticker")
        return f"https://www.fundamentus.com.br/proventos.php?papel={safe}&tipo=2"

    def _throttle(self) -> None:
        elapsed = monotonic() - self._last_request_monotonic
        remaining = self.min_request_interval_seconds - elapsed
        if remaining > 0:
            sleep(remaining)

    def fetch_html(self, ticker: str) -> str:
        self._throttle()
        with httpx.Client(timeout=self.timeout_seconds, follow_redirects=True) as client:
            response = client.get(self.build_url(ticker), headers={"User-Agent": self.user_agent})
            response.raise_for_status()
        self._last_request_monotonic = monotonic()
        return response.text

    @staticmethod
    def parse_html(html: str) -> list[DividendPayment]:
        tables = pd.read_html(StringIO(html), decimal=",", thousands=".")
        if not tables:
            return []
        target: pd.DataFrame | None = None
        for table in tables:
            names = {str(c).strip().lower() for c in table.columns}
            if "data" in names and "valor" in names and "tipo" in names:
                target = table
                break
        if target is None:
            return []

        columns = {str(c).strip().lower(): c for c in target.columns}
        date_col = columns["data"]
        value_col = columns["valor"]
        type_col = columns["tipo"]

        result: list[DividendPayment] = []
        for _, row in target.iterrows():
            try:
                day, month, year = map(int, str(row[date_col]).strip().split("/"))
                parsed_date = date(year, month, day)
                raw_value = row[value_col]
                if isinstance(raw_value, str):
                    value = float(raw_value.replace(".", "").replace(",", "."))
                else:
                    value = float(raw_value)
                kind_text = str(row[type_col]).upper()
                kind = "JCP" if "CAP" in kind_text or "JRS" in kind_text else "DIVIDEND"
                if value > 0:
                    result.append(DividendPayment(parsed_date, value, kind=kind))
            except (TypeError, ValueError):
                continue
        return sorted(result, key=lambda p: p.ex_date)

    def fetch(self, ticker: str) -> list[DividendPayment]:
        return self.parse_html(self.fetch_html(ticker))
