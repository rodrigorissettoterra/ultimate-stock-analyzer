from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from statistics import median


@dataclass(frozen=True, slots=True)
class DividendPayment:
    ex_date: date
    amount_per_share: float
    kind: str = "DIVIDEND"  # DIVIDEND or JCP
    extraordinary: bool = False


@dataclass(frozen=True, slots=True)
class DividendProfile:
    years_paid: int
    window_years: int
    regular_year_ratio: float
    max_gap_months: float | None
    payment_count: int
    ttm_amount: float
    ttm_yield: float | None
    median_annual_amount: float | None
    annual_amount_cagr: float | None
    extraordinary_share: float
    regularity_score: float
    qualifies_as_regular_payer: bool


def _month_gap(a: date, b: date) -> float:
    return (b.year - a.year) * 12 + (b.month - a.month) + (b.day - a.day) / 30.44


def _annual_totals(payments: list[DividendPayment]) -> dict[int, float]:
    totals: dict[int, float] = {}
    for p in payments:
        if not p.extraordinary:
            totals[p.ex_date.year] = totals.get(p.ex_date.year, 0.0) + p.amount_per_share
    return totals


def analyze_dividends(
    payments: list[DividendPayment],
    as_of: date,
    current_price: float | None,
    window_years: int = 5,
    min_years_paid: int = 4,
    max_allowed_gap_months: float = 18.0,
) -> DividendProfile:
    cutoff_year = as_of.year - window_years + 1
    history = sorted(
        [p for p in payments if cutoff_year <= p.ex_date.year <= as_of.year and p.ex_date <= as_of],
        key=lambda p: p.ex_date,
    )
    regular = [p for p in history if not p.extraordinary and p.amount_per_share > 0]
    annual = _annual_totals(regular)
    years_paid = len(annual)
    regular_year_ratio = years_paid / window_years if window_years else 0.0

    gaps = [_month_gap(a.ex_date, b.ex_date) for a, b in zip(regular, regular[1:])]
    max_gap = max(gaps) if gaps else None

    ttm_cutoff = date(as_of.year - 1, as_of.month, min(as_of.day, 28))
    ttm_amount = sum(p.amount_per_share for p in history if p.ex_date > ttm_cutoff)
    ttm_yield = ttm_amount / current_price if current_price and current_price > 0 else None

    annual_values = [annual[y] for y in sorted(annual)]
    med = median(annual_values) if annual_values else None
    cagr = None
    if len(annual_values) >= 2 and annual_values[0] > 0 and annual_values[-1] >= 0:
        cagr = (annual_values[-1] / annual_values[0]) ** (1 / (len(annual_values) - 1)) - 1

    total_amount = sum(max(p.amount_per_share, 0) for p in history)
    extraordinary_amount = sum(
        max(p.amount_per_share, 0) for p in history if p.extraordinary
    )
    extraordinary_share = extraordinary_amount / total_amount if total_amount > 0 else 0.0

    gap_component = 1.0
    if max_gap is not None:
        gap_component = max(0.0, min(1.0, max_allowed_gap_months / max(max_gap, 1.0)))
    count_component = min(1.0, len(regular) / max(window_years, 1))
    extraordinary_penalty = max(0.0, 1.0 - extraordinary_share)
    regularity_score = 100 * (
        0.55 * regular_year_ratio
        + 0.25 * gap_component
        + 0.10 * count_component
        + 0.10 * extraordinary_penalty
    )
    qualifies = years_paid >= min_years_paid and (max_gap is None or max_gap <= max_allowed_gap_months)

    return DividendProfile(
        years_paid=years_paid,
        window_years=window_years,
        regular_year_ratio=regular_year_ratio,
        max_gap_months=max_gap,
        payment_count=len(regular),
        ttm_amount=ttm_amount,
        ttm_yield=ttm_yield,
        median_annual_amount=med,
        annual_amount_cagr=cagr,
        extraordinary_share=extraordinary_share,
        regularity_score=regularity_score,
        qualifies_as_regular_payer=qualifies,
    )
