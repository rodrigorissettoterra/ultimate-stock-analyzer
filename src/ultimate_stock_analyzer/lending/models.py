from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True, slots=True)
class LoanBalanceRecord:
    """Daily securities-lending flow published by B3.

    Rates are stored as annual decimal rates: 0.05 means 5% p.a.
    This record is a daily flow and must not be confused with open-position stock.
    """

    report_date: date
    ticker: str
    isin: str | None
    asset: str | None
    market: str | None
    contracts_day: int
    shares_day: float
    value_day: float
    donor_min_rate: float | None
    donor_avg_rate: float | None
    donor_max_rate: float | None
    taker_min_rate: float | None
    taker_avg_rate: float | None
    taker_max_rate: float | None
    source: str = "B3_LOAN_BALANCE"


@dataclass(frozen=True, slots=True)
class LendingOpenPositionRecord:
    """End-of-day stock of securities-lending positions published by B3."""

    report_date: date
    ticker: str
    isin: str | None
    asset: str | None
    balance_quantity: float
    trade_average_price: float | None
    price_factor: float | None
    balance_value: float | None
    market: str | None = None
    source: str = "B3_LENDING_OPEN_POSITION"
