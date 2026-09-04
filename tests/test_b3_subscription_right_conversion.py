from datetime import UTC, date, datetime

import pytest

from ultimate_stock_analyzer.backtesting.b3_event_aware_coverage import (
    B3_SUPPLEMENT_HISTORICAL_COMPLETENESS_UNPROVEN,
    UNSUPPORTED_RELEVANT_SUBSCRIPTION,
    audit_b3_event_aware_coverage,
)
from ultimate_stock_analyzer.backtesting.b3_subscription_right_conversion import (
    SUBSCRIPTION_RIGHT_AVAILABILITY_UNKNOWN,
    SUBSCRIPTION_RIGHT_CONVERTED,
    SUBSCRIPTION_RIGHT_ISIN_MISMATCH,
    convert_b3_subscription_right,
)
from ultimate_stock_analyzer.backtesting.historical_event_dataset import (
    materialize_historical_event_dataset,
)
from ultimate_stock_analyzer.collectors.b3_corporate_actions import (
    B3SubscriptionContractRecord,
)
from ultimate_stock_analyzer.market.prices import PriceBar


def _bar(trading_date: date, close: float, *, isin: str = "BRTESTACNOR0") -> PriceBar:
    return PriceBar(
        ticker="TEST3",
        trade_date=trading_date,
        open=close,
        high=close,
        low=close,
        close=close,
        volume=1000.0,
        trades=10,
        quantity=100,
        isin=isin,
    )


def _bars() -> list[PriceBar]:
    return [
        _bar(date(2025, 1, 2), 10.0),
        _bar(date(2025, 1, 3), 9.5),
    ]


def _event(
    *,
    percentage: float = 10.0,
    price_unit: float = 5.0,
    approved_on: date | None = date(2025, 1, 1),
    asset_issued: str | None = "BRTESTACNOR0",
    isin_code: str | None = "BRTESTACNOR0",
) -> B3SubscriptionContractRecord:
    return B3SubscriptionContractRecord(
        asset_issued=asset_issued,
        label="Subscricao",
        percentage=percentage,
        price_unit=price_unit,
        approved_on=approved_on,
        last_date_prior=date(2025, 1, 2),
        subscription_date=date(2025, 1, 20),
        trading_period=None,
        isin_code=isin_code,
        remarks=None,
    )


def test_same_security_subscription_uses_official_b3_value_reference_formula() -> None:
    conversion = convert_b3_subscription_right(
        ticker="TEST3",
        event=_event(),
        bars=_bars(),
    )

    expected = (0.10 / 1.10) * (10.0 - 5.0)
    assert conversion.status == SUBSCRIPTION_RIGHT_CONVERTED
    assert conversion.converted
    assert conversion.subscription_ratio == pytest.approx(0.10)
    assert conversion.value_reference_per_share == pytest.approx(expected)
    assert conversion.ex_date == date(2025, 1, 3)
    assert conversion.available_from == datetime(2025, 1, 2, tzinfo=UTC)
    assert conversion.distribution is not None
    assert conversion.distribution.amount_per_share == pytest.approx(expected)


def test_subscription_without_public_availability_fails_closed() -> None:
    conversion = convert_b3_subscription_right(
        ticker="TEST3",
        event=_event(approved_on=None),
        bars=_bars(),
    )

    assert conversion.status == SUBSCRIPTION_RIGHT_AVAILABILITY_UNKNOWN
    assert not conversion.converted
    assert not conversion.point_in_time_eligible
    assert conversion.distribution is None


def test_subscription_security_mismatch_fails_closed() -> None:
    conversion = convert_b3_subscription_right(
        ticker="TEST3",
        event=_event(asset_issued="BROTHERACNOR0", isin_code="BROTHERACNOR0"),
        bars=_bars(),
    )

    assert conversion.status == SUBSCRIPTION_RIGHT_ISIN_MISMATCH
    assert not conversion.converted


def test_out_of_money_subscription_has_zero_economic_distribution() -> None:
    conversion = convert_b3_subscription_right(
        ticker="TEST3",
        event=_event(price_unit=11.0),
        bars=_bars(),
    )

    assert conversion.status == SUBSCRIPTION_RIGHT_CONVERTED
    assert conversion.converted
    assert conversion.value_reference_per_share == 0.0
    assert conversion.distribution is not None
    assert conversion.distribution.amount_per_share == 0.0


def test_supported_subscription_flows_into_event_dataset_without_readiness_promotion() -> None:
    payload: dict[str, object] = {
        "stockDividends": [],
        "cashDividends": [],
        "subscriptions": [
            {
                "assetIssued": "BRTESTACNOR0",
                "label": "Subscricao",
                "percentage": 10.0,
                "priceUnit": 5.0,
                "approvedOn": "2025-01-01",
                "lastDatePrior": "2025-01-02",
                "subscriptionDate": "2025-01-20",
                "isinCode": "BRTESTACNOR0",
            }
        ],
    }
    bars = _bars()
    audit = audit_b3_event_aware_coverage(
        issuing_company="TEST",
        ticker="TEST3",
        payload=payload,
        bars=bars,
        start_date=date(2025, 1, 1),
        end_date=date(2025, 12, 31),
        generated_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    dataset = materialize_historical_event_dataset(audits=[audit], bars=bars)

    assert audit.relevant_subscription_count == 1
    assert audit.converted_subscription_right_count == 1
    assert audit.blocked_subscription_right_count == 0
    assert len(audit.subscription_conversions) == 1
    assert UNSUPPORTED_RELEVANT_SUBSCRIPTION not in audit.observed_blockers
    assert audit.observed_event_coverage_complete
    assert B3_SUPPLEMENT_HISTORICAL_COMPLETENESS_UNPROVEN in audit.strict_blockers
    assert len(dataset.distributions) == 1
    assert dataset.distributions[0].amount_per_share == pytest.approx((0.10 / 1.10) * 5.0)
    assert B3_SUPPLEMENT_HISTORICAL_COMPLETENESS_UNPROVEN in dataset.strict_blockers
    assert not dataset.historical_source_completeness_proven
    assert not dataset.strict_event_aware_backtest_ready
    assert not dataset.readiness_promotion_allowed
