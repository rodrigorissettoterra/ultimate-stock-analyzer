from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from math import isfinite

from ultimate_stock_analyzer.dividends.regularity import (
    DividendPayment,
    analyze_dividends,
    point_in_time_payments,
)


@dataclass(frozen=True, slots=True)
class InsuranceDividendMetrics:
    """PIT-safe insurer dividend features derived from official B3 cash distributions."""

    as_of: datetime
    dividend_regularity: float | None
    dividend_cagr_5y: float | None
    cagr_start_year: int | None
    cagr_end_year: int | None
    complete_cagr_history: bool
    visible_payment_count: int
    point_in_time_eligible: bool = True
    source: str = "B3_PUBLIC_LISTED_COMPANIES_DERIVED"


def derive_insurance_dividend_metrics(
    payments: list[DividendPayment],
    *,
    as_of: datetime,
) -> InsuranceDividendMetrics:
    """Derive insurer dividend regularity and strict five-year distribution CAGR.

    Historical scoring only sees payments whose ``available_from`` was known by the
    requested timestamp. The existing dividend regularity model is reused unchanged.
    CAGR uses six consecutive *completed* calendar years, which creates an exact
    five-year endpoint interval. Every year must contain a positive regular DIVIDEND/JCP
    distribution; missing years or non-positive endpoints remain UNKNOWN.

    The caller must provide payments already scoped to one security/issuer economic
    exposure. No ticker/name matching happens in this adapter.
    """

    cutoff = _aware(as_of)
    visible = point_in_time_payments(
        payments,
        as_of=cutoff,
        require_known_availability=True,
    )
    profile = analyze_dividends(
        visible,
        as_of=cutoff.date(),
        current_price=None,
        window_years=5,
    )
    cagr, start_year, end_year, complete_history = _strict_completed_distribution_cagr(
        visible,
        as_of=cutoff.date(),
    )
    regularity = profile.regularity_score
    if not isfinite(regularity):
        regularity = None

    return InsuranceDividendMetrics(
        as_of=cutoff,
        dividend_regularity=regularity,
        dividend_cagr_5y=cagr,
        cagr_start_year=start_year,
        cagr_end_year=end_year,
        complete_cagr_history=complete_history,
        visible_payment_count=len(visible),
    )


def insurance_dividend_features(
    payments: list[DividendPayment],
    *,
    as_of: datetime,
) -> dict[str, float | None]:
    """Return only insurer dividend metrics with independently safe semantics.

    ``dividend_sustainability`` intentionally remains absent: the generic corporate
    sustainability model depends materially on free cash flow, which is not a safe
    insurer analogue and must not be reused merely to increase coverage.
    """

    metrics = derive_insurance_dividend_metrics(payments, as_of=as_of)
    return {
        "dividend_regularity": metrics.dividend_regularity,
        "dividend_cagr_5y": metrics.dividend_cagr_5y,
    }


def _strict_completed_distribution_cagr(
    payments: list[DividendPayment],
    *,
    as_of: date,
) -> tuple[float | None, int, int, bool]:
    end_year = as_of.year if as_of.month == 12 and as_of.day == 31 else as_of.year - 1
    start_year = end_year - 5
    annual = {year: 0.0 for year in range(start_year, end_year + 1)}

    for payment in payments:
        if payment.extraordinary:
            continue
        if payment.kind.upper() not in {"DIVIDEND", "JCP"}:
            continue
        if payment.amount_per_share <= 0.0 or not isfinite(payment.amount_per_share):
            continue
        if start_year <= payment.ex_date.year <= end_year:
            annual[payment.ex_date.year] += payment.amount_per_share

    if any(not isfinite(value) or value <= 0.0 for value in annual.values()):
        return None, start_year, end_year, False

    start_value = annual[start_year]
    end_value = annual[end_year]
    cagr = (end_value / start_value) ** (1.0 / 5.0) - 1.0
    if not isfinite(cagr):
        return None, start_year, end_year, True
    return cagr, start_year, end_year, True


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
