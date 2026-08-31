from __future__ import annotations

import io
import zipfile
from dataclasses import dataclass, field
from datetime import date

from ultimate_stock_analyzer.market.prices import B3CotahistCollector


@dataclass(frozen=True, slots=True)
class B3CotahistSecurityObservation:
    ticker: str
    trade_date: date
    market_code: int
    specification: str | None
    isin: str | None
    source: str = "B3_COTAHIST"


@dataclass(slots=True)
class B3CotahistSecurityObserver:
    collector: B3CotahistCollector = field(default_factory=B3CotahistCollector)

    def fetch_year(
        self,
        year: int,
        *,
        tickers: set[str] | None = None,
    ) -> list[B3CotahistSecurityObservation]:
        archive = self.collector.download_year_archive(year)
        return self.parse_year_archive(archive, tickers=tickers)

    def parse_year_archive(
        self,
        content: bytes,
        *,
        tickers: set[str] | None = None,
    ) -> list[B3CotahistSecurityObservation]:
        requested = None
        if tickers is not None:
            requested = {ticker.strip().upper() for ticker in tickers if ticker.strip()}
            if not requested:
                raise ValueError("tickers must contain at least one non-blank ticker")

        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            members = [name for name in archive.namelist() if name.upper().endswith(".TXT")]
            if not members:
                raise ValueError("B3 COTAHIST archive contains no TXT file")
            with archive.open(members[0]) as file:
                text = file.read().decode("latin1")
        return parse_cotahist_security_text(text, tickers=requested)


def parse_cotahist_security_text(
    text: str,
    *,
    tickers: set[str] | None = None,
) -> list[B3CotahistSecurityObservation]:
    requested = {ticker.upper() for ticker in tickers} if tickers is not None else None
    observations: list[B3CotahistSecurityObservation] = []
    for line in text.splitlines():
        observation = parse_cotahist_security_line(line)
        if observation is None:
            continue
        if requested is not None and observation.ticker not in requested:
            continue
        observations.append(observation)
    return sorted(observations, key=lambda item: (item.trade_date, item.ticker))


def parse_cotahist_security_line(line: str) -> B3CotahistSecurityObservation | None:
    record = line.rstrip("\r\n")
    if len(record) < 245 or record[0:2] != "01":
        return None
    market_text = record[24:27].strip()
    if not market_text:
        return None
    market_code = int(market_text)
    if market_code != 10:
        return None
    ticker = record[12:24].strip().upper()
    if not ticker:
        return None
    raw_date = record[2:10]
    trade_date = date(int(raw_date[0:4]), int(raw_date[4:6]), int(raw_date[6:8]))
    return B3CotahistSecurityObservation(
        ticker=ticker,
        trade_date=trade_date,
        market_code=market_code,
        specification=record[39:49].strip() or None,
        isin=record[230:242].strip() or None,
    )
