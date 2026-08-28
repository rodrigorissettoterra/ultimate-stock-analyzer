import base64
import json
from datetime import UTC, date, datetime

import pytest

from ultimate_stock_analyzer.collectors.b3_dividends import B3DividendCollector
from ultimate_stock_analyzer.dividends.regularity import (
    DividendPayment,
    analyze_dividends,
    point_in_time_payments,
)
from ultimate_stock_analyzer.dividends.sustainability import (
    analyze_dividend_sustainability,
)


def test_b3_collector_encodes_official_public_page_parameters() -> None:
    collector = B3DividendCollector()
    encoded = collector.build_url("abev").rsplit("/", 1)[-1]
    decoded = json.loads(base64.b64decode(encoded).decode("utf-8"))

    assert decoded == {"issuingCompany": "ABEV", "language": "pt-br"}


def test_b3_cash_dividend_parser_preserves_date_basis_and_availability() -> None:
    payload = {
        "cashDividends": [
            {
                "assetIssued": "ABEV3",
                "paymentDate": "15/04/2026",
                "rate": "0,25000000000",
                "relatedTo": "Exercício 2025",
                "approvedOn": "20/03/2026",
                "isinCode": "BRABEVACNOR1",
                "label": "JRS CAP PROPRIO",
                "lastDatePrior": "25/03/2026",
                "remarks": "",
            }
        ]
    }

    payments = B3DividendCollector.parse_cash_dividends(
        payload,
        collected_at=datetime(2026, 8, 28, tzinfo=UTC),
        source_url="https://example.invalid/source",
    )

    assert len(payments) == 1
    assert payments[0].ticker == "ABEV3"
    assert payments[0].kind == "JCP"
    assert payments[0].amount_per_share == pytest.approx(0.25)
    assert payments[0].date_basis == "LAST_DATE_PRIOR_TO_EX"
    assert payments[0].available_from == datetime(2026, 3, 21, tzinfo=UTC)


def test_point_in_time_dividends_exclude_future_announcements() -> None:
    payments = [
        DividendPayment(
            date(2026, 3, 25),
            0.25,
            available_from=datetime(2026, 3, 21, tzinfo=UTC),
        ),
        DividendPayment(
            date(2026, 6, 25),
            0.30,
            available_from=datetime(2026, 6, 21, tzinfo=UTC),
        ),
    ]

    visible = point_in_time_payments(
        payments,
        as_of=datetime(2026, 5, 1, tzinfo=UTC),
    )

    assert len(visible) == 1
    assert visible[0].amount_per_share == pytest.approx(0.25)


def test_sustainability_rewards_regular_covered_distributions() -> None:
    payments = [
        DividendPayment(date(year, 6, 30), 1.0)
        for year in range(2022, 2027)
    ]
    profile = analyze_dividends(
        payments,
        as_of=date(2026, 12, 31),
        current_price=20.0,
    )
    sustainability = analyze_dividend_sustainability(
        profile,
        earnings_per_share_ttm=2.0,
        fcf_per_share_ttm=2.5,
    )

    assert profile.qualifies_as_regular_payer
    assert sustainability.earnings_payout == pytest.approx(0.5)
    assert sustainability.fcf_payout == pytest.approx(0.4)
    assert sustainability.sustainability_score >= 90
    assert sustainability.flags == ()


def test_sustainability_penalizes_distribution_without_cash_coverage() -> None:
    payments = [
        DividendPayment(date(year, 6, 30), 1.0)
        for year in range(2022, 2027)
    ]
    profile = analyze_dividends(
        payments,
        as_of=date(2026, 12, 31),
        current_price=20.0,
    )
    sustainability = analyze_dividend_sustainability(
        profile,
        earnings_per_share_ttm=0.5,
        fcf_per_share_ttm=-0.2,
    )

    assert "DISTRIBUTION_EXCEEDS_EARNINGS" in sustainability.flags
    assert "NON_POSITIVE_FCF" in sustainability.flags
    assert sustainability.sustainability_score < 75
