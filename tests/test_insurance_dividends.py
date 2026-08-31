from datetime import UTC, date, datetime

import pytest

from ultimate_stock_analyzer.dividends.regularity import DividendPayment
from ultimate_stock_analyzer.scoring.insurance_dividends import (
    derive_insurance_dividend_metrics,
    insurance_dividend_features,
)


def _payment(
    year: int,
    amount: float,
    *,
    available_year: int | None = None,
    extraordinary: bool = False,
    kind: str = "DIVIDEND",
) -> DividendPayment:
    available = available_year if available_year is not None else year
    return DividendPayment(
        ex_date=date(year, 6, 30),
        amount_per_share=amount,
        kind=kind,
        extraordinary=extraordinary,
        available_from=datetime(available, 6, 1, tzinfo=UTC),
        source="B3_PUBLIC_LISTED_COMPANIES",
    )


def test_features_map_regularity_and_exact_five_year_cagr() -> None:
    payments = [_payment(year, 1.1 ** (year - 2019)) for year in range(2019, 2025)]

    metrics = derive_insurance_dividend_metrics(
        payments,
        as_of=datetime(2025, 8, 31, tzinfo=UTC),
    )

    assert metrics.complete_cagr_history is True
    assert metrics.cagr_start_year == 2019
    assert metrics.cagr_end_year == 2024
    assert metrics.dividend_cagr_5y == pytest.approx(0.1)
    assert metrics.dividend_regularity is not None
    assert 0.0 <= metrics.dividend_regularity <= 100.0
    assert metrics.point_in_time_eligible is True

    features = insurance_dividend_features(
        payments,
        as_of=datetime(2025, 8, 31, tzinfo=UTC),
    )
    assert set(features) == {"dividend_regularity", "dividend_cagr_5y"}
    assert "dividend_sustainability" not in features


def test_cagr_uses_current_year_only_when_december_31_is_complete() -> None:
    payments = [_payment(year, 1.0) for year in range(2020, 2026)]

    before_year_end = derive_insurance_dividend_metrics(
        payments,
        as_of=datetime(2025, 12, 30, tzinfo=UTC),
    )
    at_year_end = derive_insurance_dividend_metrics(
        payments,
        as_of=datetime(2025, 12, 31, 23, 59, tzinfo=UTC),
    )

    assert before_year_end.cagr_start_year == 2019
    assert before_year_end.cagr_end_year == 2024
    assert before_year_end.complete_cagr_history is False
    assert at_year_end.cagr_start_year == 2020
    assert at_year_end.cagr_end_year == 2025
    assert at_year_end.complete_cagr_history is True
    assert at_year_end.dividend_cagr_5y == pytest.approx(0.0)


def test_missing_distribution_year_keeps_cagr_unknown() -> None:
    payments = [_payment(year, 1.0) for year in (2019, 2020, 2021, 2023, 2024)]
    metrics = derive_insurance_dividend_metrics(
        payments,
        as_of=datetime(2025, 8, 31, tzinfo=UTC),
    )
    assert metrics.complete_cagr_history is False
    assert metrics.dividend_cagr_5y is None


def test_extraordinary_distribution_does_not_fill_cagr_history() -> None:
    payments = [_payment(year, 1.0) for year in (2019, 2020, 2021, 2023, 2024)]
    payments.append(_payment(2022, 10.0, extraordinary=True))
    metrics = derive_insurance_dividend_metrics(
        payments,
        as_of=datetime(2025, 8, 31, tzinfo=UTC),
    )
    assert metrics.complete_cagr_history is False
    assert metrics.dividend_cagr_5y is None


def test_jcp_is_eligible_for_dividend_metrics() -> None:
    payments = [_payment(year, 1.0, kind="JCP") for year in range(2019, 2025)]
    metrics = derive_insurance_dividend_metrics(
        payments,
        as_of=datetime(2025, 8, 31, tzinfo=UTC),
    )
    assert metrics.complete_cagr_history is True
    assert metrics.dividend_cagr_5y == pytest.approx(0.0)


def test_future_availability_is_excluded_from_historical_view() -> None:
    payments = [_payment(year, 1.0) for year in range(2019, 2024)]
    payments.append(_payment(2024, 1.0, available_year=2026))

    metrics = derive_insurance_dividend_metrics(
        payments,
        as_of=datetime(2025, 8, 31, tzinfo=UTC),
    )

    assert metrics.visible_payment_count == 5
    assert metrics.complete_cagr_history is False
    assert metrics.dividend_cagr_5y is None


def test_unknown_availability_is_excluded_fail_closed() -> None:
    payments = [_payment(year, 1.0) for year in range(2019, 2024)]
    payments.append(
        DividendPayment(
            ex_date=date(2024, 6, 30),
            amount_per_share=1.0,
            kind="DIVIDEND",
            available_from=None,
        )
    )
    metrics = derive_insurance_dividend_metrics(
        payments,
        as_of=datetime(2025, 8, 31, tzinfo=UTC),
    )
    assert metrics.visible_payment_count == 5
    assert metrics.complete_cagr_history is False


def test_naive_as_of_is_normalized_to_utc() -> None:
    payments = [_payment(year, 1.0) for year in range(2019, 2025)]
    metrics = derive_insurance_dividend_metrics(
        payments,
        as_of=datetime(2025, 8, 31),
    )
    assert metrics.as_of.tzinfo == UTC
