from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from itertools import pairwise
from statistics import mean, median, stdev

ELIGIBLE_CASH_KINDS = frozenset({"DIVIDEND", "JCP"})


@dataclass(frozen=True, slots=True)
class DividendPayment:
    ex_date: date
    amount_per_share: float
    kind: str = "DIVIDEND"
    extraordinary: bool = False
    ticker: str | None = None
    isin: str | None = None
    declared_date: date | None = None
    payment_date: date | None = None
    available_from: datetime | None = None
    collected_at: datetime | None = None
    source: str | None = None
    source_url: str | None = None
    related_to: str | None = None
    remarks: str | None = None
    date_basis: str = "EX_DATE"


@dataclass(frozen=True, slots=True)
class DividendProfile:
    years_paid: int
    completed_years_paid: int
    window_years: int
    regular_year_ratio: float
    longest_annual_streak: int
    max_gap_months: float | None
    payment_count: int
    ttm_amount: float
    ttm_regular_amount: float
    ttm_extraordinary_amount: float
    ttm_yield: float | None
    median_annual_amount: float | None
    annual_amount_cagr: float | None
    annual_amount_cv: float | None
    cut_years: int
    annual_regular_amounts: tuple[tuple[int, float], ...]
    completed_annual_amounts: tuple[tuple[int, float], ...]
    extraordinary_share: float
    regularity_score: float
    qualifies_as_regular_payer: bool


def point_in_time_payments(
    payments: list[DividendPayment],
    *,
    as_of: datetime,
    require_known_availability: bool = True,
) -> list[DividendPayment]:
    cutoff = _aware(as_of)
    visible: list[DividendPayment] = []
    for payment in payments:
        if payment.available_from is None:
            if require_known_availability:
                continue
            if payment.ex_date <= cutoff.date():
                visible.append(payment)
            continue
        if _aware(payment.available_from) <= cutoff:
            visible.append(payment)
    return sorted(visible, key=lambda payment: payment.ex_date)


def _month_gap(a: date, b: date) -> float:
    return (b.year - a.year) * 12 + (b.month - a.month) + (b.day - a.day) / 30.44


def _annual_totals(payments: list[DividendPayment]) -> dict[int, float]:
    totals: dict[int, float] = {}
    for payment in payments:
        if payment.extraordinary or payment.kind.upper() not in ELIGIBLE_CASH_KINDS:
            continue
        totals[payment.ex_date.year] = (
            totals.get(payment.ex_date.year, 0.0) + payment.amount_per_share
        )
    return totals


def _completed_annual_totals(annual: dict[int, float], as_of: date) -> dict[int, float]:
    include_current = as_of.month == 12 and as_of.day == 31
    return {
        year: amount
        for year, amount in annual.items()
        if year < as_of.year or (year == as_of.year and include_current)
    }


def _longest_streak(years: list[int]) -> int:
    if not years:
        return 0
    longest = 1
    current = 1
    for previous, current_year in pairwise(sorted(years)):
        if current_year == previous + 1:
            current += 1
            longest = max(longest, current)
        else:
            current = 1
    return longest


def _coefficient_of_variation(values: list[float]) -> float | None:
    if len(values) < 2:
        return None
    avg = mean(values)
    if avg == 0:
        return None
    return stdev(values) / abs(avg)


def _annual_cagr(annual: dict[int, float]) -> float | None:
    years = sorted(annual)
    if len(years) < 2:
        return None
    first_year = years[0]
    last_year = years[-1]
    first = annual[first_year]
    last = annual[last_year]
    elapsed = last_year - first_year
    if elapsed <= 0 or first <= 0 or last < 0:
        return None
    return (last / first) ** (1 / elapsed) - 1


def _cut_years(annual: dict[int, float], threshold: float = 0.10) -> int:
    cuts = 0
    years = sorted(annual)
    for previous_year, current_year in pairwise(years):
        previous = annual[previous_year]
        current = annual[current_year]
        if previous > 0 and current < previous * (1 - threshold):
            cuts += 1
    return cuts


def analyze_dividends(
    payments: list[DividendPayment],
    as_of: date,
    current_price: float | None,
    window_years: int = 5,
    min_years_paid: int = 4,
    max_allowed_gap_months: float = 18.0,
) -> DividendProfile:
    if window_years <= 0:
        raise ValueError("window_years must be positive")
    cutoff_year = as_of.year - window_years + 1
    history = sorted(
        [
            payment
            for payment in payments
            if cutoff_year <= payment.ex_date.year <= as_of.year
            and payment.ex_date <= as_of
            and payment.amount_per_share > 0
            and payment.kind.upper() in ELIGIBLE_CASH_KINDS
        ],
        key=lambda payment: payment.ex_date,
    )
    regular = [payment for payment in history if not payment.extraordinary]
    annual = _annual_totals(regular)
    completed_annual = _completed_annual_totals(annual, as_of)
    years_paid = len(annual)
    regular_year_ratio = years_paid / window_years

    gaps = [_month_gap(a.ex_date, b.ex_date) for a, b in pairwise(regular)]
    max_gap = max(gaps) if gaps else None

    ttm_cutoff = as_of - timedelta(days=365)
    ttm = [payment for payment in history if payment.ex_date > ttm_cutoff]
    ttm_amount = sum(payment.amount_per_share for payment in ttm)
    ttm_regular_amount = sum(
        payment.amount_per_share for payment in ttm if not payment.extraordinary
    )
    ttm_extraordinary_amount = ttm_amount - ttm_regular_amount
    ttm_yield = (
        ttm_amount / current_price
        if current_price is not None and current_price > 0
        else None
    )

    completed_values = [completed_annual[year] for year in sorted(completed_annual)]
    med = median(completed_values) if completed_values else None
    annual_cagr = _annual_cagr(completed_annual)
    annual_cv = _coefficient_of_variation(completed_values)
    cut_years = _cut_years(completed_annual)

    total_amount = sum(payment.amount_per_share for payment in history)
    extraordinary_amount = sum(
        payment.amount_per_share for payment in history if payment.extraordinary
    )
    extraordinary_share = extraordinary_amount / total_amount if total_amount > 0 else 0.0

    gap_component = 1.0
    if max_gap is not None:
        gap_component = max(
            0.0,
            min(1.0, max_allowed_gap_months / max(max_gap, 1.0)),
        )
    count_component = min(1.0, len(regular) / window_years)
    extraordinary_component = max(0.0, 1.0 - extraordinary_share)
    regularity_score = 100 * (
        0.55 * regular_year_ratio
        + 0.25 * gap_component
        + 0.10 * count_component
        + 0.10 * extraordinary_component
    )
    regularity_score = max(0.0, min(100.0, regularity_score))
    qualifies = years_paid >= min_years_paid and (
        max_gap is None or max_gap <= max_allowed_gap_months
    )

    return DividendProfile(
        years_paid=years_paid,
        completed_years_paid=len(completed_annual),
        window_years=window_years,
        regular_year_ratio=regular_year_ratio,
        longest_annual_streak=_longest_streak(list(annual)),
        max_gap_months=max_gap,
        payment_count=len(regular),
        ttm_amount=ttm_amount,
        ttm_regular_amount=ttm_regular_amount,
        ttm_extraordinary_amount=ttm_extraordinary_amount,
        ttm_yield=ttm_yield,
        median_annual_amount=med,
        annual_amount_cagr=annual_cagr,
        annual_amount_cv=annual_cv,
        cut_years=cut_years,
        annual_regular_amounts=tuple(sorted(annual.items())),
        completed_annual_amounts=tuple(sorted(completed_annual.items())),
        extraordinary_share=extraordinary_share,
        regularity_score=regularity_score,
        qualifies_as_regular_payer=qualifies,
    )


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
