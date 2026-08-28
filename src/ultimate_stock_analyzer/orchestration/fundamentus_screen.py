from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date

from ultimate_stock_analyzer.collectors.fundamentus import (
    FundamentusDividendCollector,
    get_snapshot,
)
from ultimate_stock_analyzer.dividends.regularity import analyze_dividends


@dataclass(frozen=True, slots=True)
class DividendCandidate:
    ticker: str
    current_price: float
    dy_snapshot: float
    liquidity_2m: float
    years_paid: int
    max_gap_months: float | None
    regularity_score: float
    qualifies_as_regular_payer: bool

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


def select_snapshot_candidates(
    min_snapshot_dy: float = 0.0,
    min_liquidity_2m: float = 0.0,
    max_candidates: int | None = None,
) -> list[tuple[str, float, float, float]]:
    frame = get_snapshot()
    candidates: list[tuple[str, float, float, float]] = []
    for ticker, row in frame.iterrows():
        try:
            price = float(row["cotacao"])
            dy = float(row["dy"])
            liq = float(row["liq2m"])
        except (KeyError, TypeError, ValueError):
            continue
        if price <= 0 or dy <= min_snapshot_dy or liq < min_liquidity_2m:
            continue
        candidates.append((str(ticker), price, dy, liq))
    candidates.sort(key=lambda item: (item[2], item[3]), reverse=True)
    return candidates[:max_candidates] if max_candidates else candidates


def screen_regular_dividend_payers(
    as_of: date,
    collector: FundamentusDividendCollector | None = None,
    min_snapshot_dy: float = 0.0,
    min_liquidity_2m: float = 0.0,
    max_candidates: int | None = None,
) -> list[DividendCandidate]:
    collector = collector or FundamentusDividendCollector()
    selected = select_snapshot_candidates(min_snapshot_dy, min_liquidity_2m, max_candidates)
    results: list[DividendCandidate] = []
    for ticker, price, dy, liquidity in selected:
        payments = collector.fetch(ticker)
        profile = analyze_dividends(payments, as_of=as_of, current_price=price)
        if profile.qualifies_as_regular_payer:
            results.append(
                DividendCandidate(
                    ticker=ticker,
                    current_price=price,
                    dy_snapshot=dy,
                    liquidity_2m=liquidity,
                    years_paid=profile.years_paid,
                    max_gap_months=profile.max_gap_months,
                    regularity_score=profile.regularity_score,
                    qualifies_as_regular_payer=True,
                )
            )
    return sorted(results, key=lambda c: (c.regularity_score, c.dy_snapshot), reverse=True)
