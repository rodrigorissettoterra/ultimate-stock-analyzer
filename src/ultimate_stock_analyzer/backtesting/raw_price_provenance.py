from __future__ import annotations

import gzip
import hashlib
import json
from collections.abc import Iterable
from datetime import date

from ultimate_stock_analyzer.bootstrap.dataset import BootstrapDataset
from ultimate_stock_analyzer.market.prices import PriceBar


def raw_price_fingerprint(bars: Iterable[PriceBar]) -> str:
    """Fingerprint the exact raw COTAHIST bars consumed by an event-aware dataset."""
    ordered = tuple(sorted(bars, key=lambda item: (item.trade_date, item.ticker.upper())))
    if not ordered:
        raise ValueError("raw price fingerprint requires at least one PriceBar")

    digest = hashlib.sha256()
    for bar in ordered:
        payload = {
            "ticker": bar.ticker.upper(),
            "trade_date": bar.trade_date.isoformat(),
            "open": bar.open,
            "high": bar.high,
            "low": bar.low,
            "close": bar.close,
            "volume": bar.volume,
            "trades": bar.trades,
            "quantity": bar.quantity,
            "market_code": bar.market_code,
            "isin": bar.isin,
            "adjusted_close": bar.adjusted_close,
            "source": bar.source,
        }
        digest.update(
            json.dumps(
                payload,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        )
        digest.update(b"\n")
    return digest.hexdigest()


def bootstrap_raw_price_fingerprint(
    dataset: BootstrapDataset,
    *,
    start_date: date,
    end_date: date,
    tickers: Iterable[str],
) -> str:
    """Fingerprint the audited bootstrap bars for one exact universe/window."""
    requested = {ticker.strip().upper() for ticker in tickers if ticker.strip()}
    if not requested:
        raise ValueError("bootstrap price fingerprint requires at least one ticker")
    if start_date > end_date:
        raise ValueError("bootstrap price fingerprint start_date must not exceed end_date")

    bars: list[PriceBar] = []
    for artifact in dataset.manifest.artifacts:
        if artifact.name != "b3_cotahist":
            continue
        path = dataset.run_dir / artifact.path
        with gzip.open(path, "rt", encoding="utf-8") as file:
            for line_number, line in enumerate(file, start=1):
                payload = line.strip()
                if not payload:
                    continue
                try:
                    row = json.loads(payload)
                    bar = _price_bar(row)
                except (KeyError, TypeError, ValueError) as exc:
                    raise ValueError(
                        f"invalid bootstrap PriceBar at {artifact.path}:{line_number}"
                    ) from exc
                if (
                    bar.ticker.upper() in requested
                    and start_date <= bar.trade_date <= end_date
                ):
                    bars.append(bar)

    present = {bar.ticker.upper() for bar in bars}
    missing = sorted(requested - present)
    if missing:
        raise ValueError(f"bootstrap price fingerprint is missing tickers: {missing}")
    return raw_price_fingerprint(bars)


def _price_bar(row: object) -> PriceBar:
    if not isinstance(row, dict):
        raise TypeError("bootstrap price row must be an object")

    return PriceBar(
        ticker=str(row["ticker"]),
        trade_date=date.fromisoformat(str(row["trade_date"])),
        open=float(row["open"]),
        high=float(row["high"]),
        low=float(row["low"]),
        close=float(row["close"]),
        volume=float(row["volume"]),
        trades=int(row["trades"]),
        quantity=int(row["quantity"]),
        market_code=int(row.get("market_code", 10)),
        isin=_optional_string(row.get("isin")),
        best_bid=_optional_float(row.get("best_bid")),
        best_ask=_optional_float(row.get("best_ask")),
        adjusted_close=_optional_float(row.get("adjusted_close")),
        source=str(row.get("source") or "B3_COTAHIST"),
    )


def _optional_string(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _optional_float(value: object) -> float | None:
    if value is None:
        return None
    return float(value)
