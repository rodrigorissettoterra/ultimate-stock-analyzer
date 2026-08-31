from __future__ import annotations

import io
import zipfile
from collections.abc import Iterable
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime

import httpx

B3_COTAHIST_YEAR_URL = (
    "https://bvmf.bmfbovespa.com.br/InstDados/SerHist/COTAHIST_A{year}.ZIP"
)


@dataclass(frozen=True, slots=True)
class PriceBar:
    ticker: str
    trade_date: date
    open: float
    high: float
    low: float
    close: float
    volume: float
    trades: int
    quantity: int
    market_code: int = 10
    isin: str | None = None
    specification: str | None = None
    best_bid: float | None = None
    best_ask: float | None = None
    adjusted_close: float | None = None
    source: str = "B3_COTAHIST"

    @property
    def analysis_close(self) -> float:
        return self.adjusted_close if self.adjusted_close is not None else self.close

    @property
    def is_adjusted(self) -> bool:
        return self.adjusted_close is not None


def _integer(text: str) -> int:
    stripped = text.strip()
    return int(stripped) if stripped else 0


def _price(text: str) -> float:
    return _integer(text) / 100.0


def _optional_price(text: str) -> float | None:
    value = _price(text)
    return value if value > 0 else None


def _yyyymmdd(text: str) -> date:
    return date(int(text[0:4]), int(text[4:6]), int(text[6:8]))


def parse_cotahist_line(line: str, *, spot_only: bool = True) -> PriceBar | None:
    """Parse one public B3 COTAHIST fixed-width record.

    The public file contains raw historical quotes. `adjusted_close` intentionally remains
    unset because B3 states that these historical prices are not adjusted for corporate events.
    """
    record = line.rstrip("\r\n")
    if len(record) < 245 or record[0:2] != "01":
        return None
    market_code = _integer(record[24:27])
    if spot_only and market_code != 10:
        return None
    ticker = record[12:24].strip()
    if not ticker:
        return None
    return PriceBar(
        ticker=ticker,
        trade_date=_yyyymmdd(record[2:10]),
        market_code=market_code,
        open=_price(record[56:69]),
        high=_price(record[69:82]),
        low=_price(record[82:95]),
        close=_price(record[108:121]),
        best_bid=_optional_price(record[121:134]),
        best_ask=_optional_price(record[134:147]),
        trades=_integer(record[147:152]),
        quantity=_integer(record[152:170]),
        volume=_price(record[170:188]),
        isin=record[230:242].strip() or None,
        specification=record[39:49].strip() or None,
    )


def parse_cotahist_text(
    text: str,
    *,
    ticker: str | None = None,
    tickers: Iterable[str] | None = None,
    spot_only: bool = True,
) -> list[PriceBar]:
    requested = _ticker_filter(ticker=ticker, tickers=tickers)
    bars: list[PriceBar] = []
    for line in text.splitlines():
        bar = parse_cotahist_line(line, spot_only=spot_only)
        if bar is None:
            continue
        if requested is not None and bar.ticker.upper() not in requested:
            continue
        bars.append(bar)
    return sorted(bars, key=lambda item: (item.trade_date, item.ticker))


def apply_adjusted_closes(
    bars: Iterable[PriceBar],
    adjusted_by_date: dict[date, float],
) -> list[PriceBar]:
    """Attach externally derived adjusted closes without overwriting raw B3 prices."""
    output: list[PriceBar] = []
    for bar in bars:
        adjusted = adjusted_by_date.get(bar.trade_date)
        output.append(replace(bar, adjusted_close=adjusted))
    return output


@dataclass(slots=True)
class B3CotahistCollector:
    timeout_seconds: float = 60.0
    user_agent: str = "ultimate-stock-analyzer/0.9"
    max_attempts: int = 3

    def download_year_archive(self, year: int) -> bytes:
        current_year = datetime.now(UTC).year
        if year < 1986 or year > current_year:
            raise ValueError("year is outside the public B3 historical-series range")
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")

        url = B3_COTAHIST_YEAR_URL.format(year=year)
        headers = {"User-Agent": self.user_agent}
        with httpx.Client(timeout=self.timeout_seconds, follow_redirects=True) as client:
            for attempt in range(1, self.max_attempts + 1):
                try:
                    response = client.get(url, headers=headers)
                except httpx.TransportError:
                    if attempt == self.max_attempts:
                        raise
                    continue

                retryable_status = response.status_code == 429 or response.status_code >= 500
                if retryable_status and attempt < self.max_attempts:
                    continue
                response.raise_for_status()
                return response.content

        raise RuntimeError("B3 COTAHIST download exhausted without a response")

    def parse_year_archive(
        self,
        content: bytes,
        *,
        ticker: str | None = None,
        tickers: Iterable[str] | None = None,
    ) -> list[PriceBar]:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            members = [name for name in archive.namelist() if name.upper().endswith(".TXT")]
            if not members:
                raise ValueError("B3 COTAHIST archive contains no TXT file")
            with archive.open(members[0]) as file:
                text = file.read().decode("latin1")
        return parse_cotahist_text(text, ticker=ticker, tickers=tickers)

    def fetch_year(
        self,
        year: int,
        *,
        ticker: str | None = None,
        tickers: Iterable[str] | None = None,
    ) -> list[PriceBar]:
        return self.parse_year_archive(
            self.download_year_archive(year),
            ticker=ticker,
            tickers=tickers,
        )


def _ticker_filter(
    *,
    ticker: str | None,
    tickers: Iterable[str] | None,
) -> set[str] | None:
    if ticker is not None and tickers is not None:
        raise ValueError("provide ticker or tickers, not both")
    if ticker is not None:
        normalized = ticker.strip().upper()
        if not normalized:
            raise ValueError("ticker must not be blank")
        return {normalized}
    if tickers is None:
        return None
    normalized = {item.strip().upper() for item in tickers if item.strip()}
    if not normalized:
        raise ValueError("tickers must contain at least one non-blank ticker")
    return normalized
