from datetime import UTC, date, datetime

from ultimate_stock_analyzer.backtesting.b3_event_aware_coverage import (
    B3_SUPPLEMENT_HISTORICAL_COMPLETENESS_UNPROVEN,
    CASH_DISTRIBUTION_AMOUNT_INVALID,
    CASH_DISTRIBUTION_AVAILABILITY_UNKNOWN,
    CASH_DISTRIBUTION_CONVERTED,
    CASH_DISTRIBUTION_ISIN_MISMATCH,
    CASH_DISTRIBUTION_KIND_UNSUPPORTED,
    SAME_SESSION_SHARE_AND_CASH_ORDERING_UNVERIFIED,
    UNPARSED_RELEVANT_CASH_EVENT,
    UNSUPPORTED_RELEVANT_SUBSCRIPTION,
    audit_b3_event_aware_coverage,
    convert_b3_cash_distribution,
)
from ultimate_stock_analyzer.dividends.regularity import DividendPayment
from ultimate_stock_analyzer.market.prices import PriceBar


def _bar(
    trading_date: date,
    *,
    open_price: float,
    close: float,
    isin: str = "BRTESTACNOR0",
) -> PriceBar:
    return PriceBar(
        ticker="TEST3",
        trade_date=trading_date,
        open=open_price,
        high=max(open_price, close),
        low=min(open_price, close),
        close=close,
        volume=1000.0,
        trades=10,
        quantity=100,
        isin=isin,
    )


def _payment(
    *,
    com_date: date = date(2025, 1, 2),
    ticker: str | None = "BRTESTACNOR0",
    isin: str | None = "BRTESTACNOR0",
    date_basis: str = "LAST_DATE_PRIOR_TO_EX",
    kind: str = "DIVIDEND",
    amount_per_share: float = 1.0,
    available_from: datetime | None = datetime(2025, 1, 1, tzinfo=UTC),
) -> DividendPayment:
    return DividendPayment(
        ex_date=com_date,
        amount_per_share=amount_per_share,
        kind=kind,
        ticker=ticker,
        isin=isin,
        date_basis=date_basis,
        available_from=available_from,
    )


def _payload(
    *,
    cash_date: str = "2025-01-03",
    cash_label: str = "DIVIDENDO",
    include_subscription: bool = False,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "stockDividends": [
            {
                "assetIssued": "BRTESTACNOR0",
                "label": "Desdobramento",
                "factor": 300.0,
                "completeFactor": None,
                "lastDatePrior": "2025-01-02",
                "isinCode": "BRTESTACNOR0",
            },
            {
                "assetIssued": "BRTESTACNPR9",
                "label": "Grupamento",
                "factor": 0.1,
                "completeFactor": None,
                "lastDatePrior": "2025-01-02",
                "isinCode": "BRTESTACNPR9",
            },
        ],
        "cashDividends": [
            {
                "assetIssued": "BRTESTACNOR0",
                "label": cash_label,
                "rate": 1.0,
                "lastDatePrior": cash_date,
                "approvedOn": "2024-12-30",
                "isinCode": "BRTESTACNOR0",
            }
        ],
        "subscriptions": [],
    }
    if include_subscription:
        payload["subscriptions"] = [
            {
                "assetIssued": "BRTESTACNOR0",
                "label": "Subscricao",
                "percentage": 10.0,
                "priceUnit": 5.0,
                "lastDatePrior": "2025-01-03",
                "isinCode": "BRTESTACNOR0",
            }
        ]
    return payload


def _bars() -> list[PriceBar]:
    return [
        _bar(date(2025, 1, 2), open_price=39.0, close=40.0),
        _bar(date(2025, 1, 3), open_price=10.0, close=10.2),
        _bar(date(2025, 1, 6), open_price=9.1, close=9.2),
    ]


def test_cash_distribution_uses_first_actual_session_after_com_date() -> None:
    conversion = convert_b3_cash_distribution(
        ticker="TEST3",
        payment=_payment(),
        bars=[
            _bar(date(2025, 1, 2), open_price=10.0, close=10.0),
            _bar(date(2025, 1, 6), open_price=9.0, close=9.2),
        ],
    )

    assert conversion.status == CASH_DISTRIBUTION_CONVERTED
    assert conversion.converted
    assert conversion.ex_date == date(2025, 1, 6)
    assert conversion.distribution is not None
    assert conversion.distribution.ex_date == date(2025, 1, 6)
    assert conversion.point_in_time_eligible
    assert conversion.available_from == datetime(2025, 1, 1, tzinfo=UTC)


def test_cash_distribution_isin_conflict_fails_closed() -> None:
    conversion = convert_b3_cash_distribution(
        ticker="TEST3",
        payment=_payment(isin="BRCASH000000"),
        bars=[
            _bar(date(2025, 1, 2), open_price=10.0, close=10.0),
            _bar(date(2025, 1, 3), open_price=9.0, close=9.2),
        ],
    )

    assert conversion.status == CASH_DISTRIBUTION_ISIN_MISMATCH
    assert not conversion.converted
    assert conversion.distribution is None


def test_cash_distribution_contract_rejects_unknown_kind_and_non_positive_amount() -> None:
    bars = [
        _bar(date(2025, 1, 2), open_price=10.0, close=10.0),
        _bar(date(2025, 1, 3), open_price=9.0, close=9.2),
    ]

    unsupported = convert_b3_cash_distribution(
        ticker="TEST3",
        payment=_payment(kind="OTHER"),
        bars=bars,
    )
    invalid_amount = convert_b3_cash_distribution(
        ticker="TEST3",
        payment=_payment(amount_per_share=0.0),
        bars=bars,
    )

    assert unsupported.status == CASH_DISTRIBUTION_KIND_UNSUPPORTED
    assert not unsupported.converted
    assert invalid_amount.status == CASH_DISTRIBUTION_AMOUNT_INVALID
    assert not invalid_amount.converted


def test_cash_distribution_without_availability_is_not_point_in_time_eligible() -> None:
    conversion = convert_b3_cash_distribution(
        ticker="TEST3",
        payment=_payment(available_from=None),
        bars=[
            _bar(date(2025, 1, 2), open_price=10.0, close=10.0),
            _bar(date(2025, 1, 3), open_price=9.0, close=9.2),
        ],
    )

    assert conversion.status == CASH_DISTRIBUTION_AVAILABILITY_UNKNOWN
    assert not conversion.point_in_time_eligible
    assert not conversion.converted


def test_live_b3_asset_issued_isin_shape_targets_the_matching_security() -> None:
    audit = audit_b3_event_aware_coverage(
        issuing_company="TEST",
        ticker="TEST3",
        payload=_payload(),
        bars=_bars(),
        start_date=date(2025, 1, 1),
        end_date=date(2025, 12, 31),
        generated_at=datetime(2026, 1, 1, tzinfo=UTC),
    )

    assert audit.relevant_stock_event_count == 1
    assert audit.relevant_cash_event_count == 1
    assert audit.ambiguous_event_scope_count == 0
    assert audit.event_identity_mismatch_count == 0


def test_observed_events_can_be_complete_without_promoting_strict_readiness() -> None:
    audit = audit_b3_event_aware_coverage(
        issuing_company="TEST",
        ticker="TEST3",
        payload=_payload(),
        bars=_bars(),
        start_date=date(2025, 1, 1),
        end_date=date(2025, 12, 31),
        generated_at=datetime(2026, 1, 1, tzinfo=UTC),
    )

    assert audit.relevant_stock_event_count == 1
    assert audit.converted_share_action_count == 1
    assert audit.relevant_cash_event_count == 1
    assert audit.converted_cash_distribution_count == 1
    assert audit.price_bar_count == 3
    assert audit.observed_event_coverage_complete
    assert not audit.observed_blockers
    assert B3_SUPPLEMENT_HISTORICAL_COMPLETENESS_UNPROVEN in audit.strict_blockers
    assert not audit.historical_source_completeness_proven
    assert not audit.event_aware_return_path_ready
    assert not audit.strict_event_aware_backtest_ready
    assert not audit.readiness_promotion_allowed
    assert not audit.price_series_blocker_removed


def test_subscription_and_unparsed_cash_event_remain_explicit_blockers() -> None:
    audit = audit_b3_event_aware_coverage(
        issuing_company="TEST",
        ticker="TEST3",
        payload=_payload(
            cash_label="RENDIMENTO ESPECIAL",
            include_subscription=True,
        ),
        bars=_bars(),
        start_date=date(2025, 1, 1),
        end_date=date(2025, 12, 31),
        generated_at=datetime(2026, 1, 1, tzinfo=UTC),
    )

    assert UNPARSED_RELEVANT_CASH_EVENT in audit.observed_blockers
    assert UNSUPPORTED_RELEVANT_SUBSCRIPTION in audit.observed_blockers
    assert audit.relevant_cash_event_count == 1
    assert audit.parsed_relevant_cash_event_count == 0
    assert audit.blocked_cash_distribution_count == 1
    assert audit.relevant_subscription_count == 1
    assert not audit.observed_event_coverage_complete


def test_same_ex_session_share_and_cash_ordering_is_not_assumed() -> None:
    audit = audit_b3_event_aware_coverage(
        issuing_company="TEST",
        ticker="TEST3",
        payload=_payload(cash_date="2025-01-02"),
        bars=_bars(),
        start_date=date(2025, 1, 1),
        end_date=date(2025, 12, 31),
        generated_at=datetime(2026, 1, 1, tzinfo=UTC),
    )

    assert SAME_SESSION_SHARE_AND_CASH_ORDERING_UNVERIFIED in audit.observed_blockers
    assert not audit.observed_event_coverage_complete
