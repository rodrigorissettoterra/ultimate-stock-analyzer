from datetime import UTC, date, datetime

import pytest

from ultimate_stock_analyzer.backtesting.b3_event_aware_coverage import (
    B3EventAwareCoverageAudit,
    B3_SUPPLEMENT_HISTORICAL_COMPLETENESS_UNPROVEN,
    audit_b3_event_aware_coverage,
)
from ultimate_stock_analyzer.backtesting.cvm_ipe_corporate_action_ledger import (
    audit_cvm_ipe_corporate_action_ledger,
)
from ultimate_stock_analyzer.backtesting.historical_event_dataset import (
    CVM_IPE_OBSERVED_EVENT_CORROBORATION_INCOMPLETE,
    DIAGNOSTIC_EVENT_AWARE_BACKTEST,
    STRICT_EVENT_AWARE_DATASET_REQUIRED,
    compare_raw_and_event_aware_m15,
    materialize_historical_event_dataset,
    run_event_aware_m15_backtest,
)
from ultimate_stock_analyzer.backtesting.models import (
    BacktestPolicy,
    ScoreSnapshot,
    UniverseMembership,
)
from ultimate_stock_analyzer.market.prices import PriceBar

GENERATED_AT = datetime(2026, 1, 1, tzinfo=UTC)
START = date(2025, 1, 1)
END = date(2025, 12, 31)


def _bar(
    ticker: str,
    trading_date: date,
    close: float,
    *,
    open_price: float | None = None,
    isin: str | None = None,
    adjusted_close: float | None = None,
) -> PriceBar:
    opening = close if open_price is None else open_price
    return PriceBar(
        ticker=ticker,
        trade_date=trading_date,
        open=opening,
        high=max(opening, close),
        low=min(opening, close),
        close=close,
        volume=1000.0,
        trades=10,
        quantity=100,
        isin=isin,
        adjusted_close=adjusted_close,
    )


def _split_payload() -> dict[str, object]:
    return {
        "stockDividends": [
            {
                "assetIssued": "BRTESTACNOR0",
                "label": "Desdobramento",
                "factor": 300.0,
                "completeFactor": None,
                "approvedOn": "2024-12-30",
                "lastDatePrior": "2025-01-02",
                "isinCode": "BRTESTACNOR0",
            }
        ],
        "cashDividends": [],
        "subscriptions": [],
    }


def _empty_payload() -> dict[str, object]:
    return {"stockDividends": [], "cashDividends": [], "subscriptions": []}


def _bars() -> list[PriceBar]:
    return [
        _bar("TEST3", date(2025, 1, 2), 40.0, open_price=39.0, isin="BRTESTACNOR0"),
        _bar("BENCH3", date(2025, 1, 2), 10.0, isin="BRBENCHACNOR0"),
        _bar("TEST3", date(2025, 1, 3), 10.0, open_price=10.0, isin="BRTESTACNOR0"),
        _bar("BENCH3", date(2025, 1, 3), 10.0, isin="BRBENCHACNOR0"),
        _bar("TEST3", date(2025, 1, 6), 10.2, open_price=10.1, isin="BRTESTACNOR0"),
        _bar("BENCH3", date(2025, 1, 6), 10.1, isin="BRBENCHACNOR0"),
    ]


def _audits() -> tuple[B3EventAwareCoverageAudit, B3EventAwareCoverageAudit]:
    bars = _bars()
    test = audit_b3_event_aware_coverage(
        issuing_company="TEST",
        ticker="TEST3",
        payload=_split_payload(),
        bars=bars,
        start_date=START,
        end_date=END,
        generated_at=GENERATED_AT,
    )
    benchmark = audit_b3_event_aware_coverage(
        issuing_company="BENCH",
        ticker="BENCH3",
        payload=_empty_payload(),
        bars=bars,
        start_date=START,
        end_date=END,
        generated_at=GENERATED_AT,
    )
    return test, benchmark


def _scores() -> list[ScoreSnapshot]:
    available = datetime(2025, 1, 1, tzinfo=UTC)
    return [
        ScoreSnapshot(
            ticker="TEST3",
            reference_date=date(2025, 1, 1),
            available_at=available,
            investment_score=90.0,
            model_version="fixture",
        ),
        ScoreSnapshot(
            ticker="BENCH3",
            reference_date=date(2025, 1, 1),
            available_at=available,
            investment_score=10.0,
            model_version="fixture",
        ),
    ]


def _memberships() -> list[UniverseMembership]:
    return [
        UniverseMembership(ticker="TEST3", start_date=START),
        UniverseMembership(ticker="BENCH3", start_date=START),
    ]


def test_materialization_keeps_raw_prices_and_extracts_validated_share_actions() -> None:
    test, benchmark = _audits()
    dataset = materialize_historical_event_dataset(
        audits=[test, benchmark],
        bars=_bars(),
    )

    assert dataset.raw_price_bar_count == 6
    assert len(dataset.raw_price_fingerprint_sha256) == 64
    assert len(dataset.share_actions) == 1
    assert dataset.share_actions[0].ticker == "TEST3"
    assert dataset.share_actions[0].ex_date == date(2025, 1, 3)
    assert dataset.share_actions[0].ratio_new_per_old == pytest.approx(4.0)
    assert all(point.close in {40.0, 10.0, 10.2, 10.1} for point in dataset.prices)
    assert dataset.raw_price_series_preserved
    assert not dataset.price_adjustment_applied
    assert not dataset.price_series_blocker_removed
    assert not dataset.readiness_promotion_allowed


def test_m15_adapter_removes_split_discontinuity_only_in_explicit_diagnostic_mode() -> None:
    test, benchmark = _audits()
    dataset = materialize_historical_event_dataset(
        audits=[test, benchmark],
        bars=_bars(),
    )
    policy = BacktestPolicy(
        top_n=1,
        transaction_cost_bps=0.0,
        slippage_bps=0.0,
    )
    comparison = compare_raw_and_event_aware_m15(
        dataset=dataset,
        rebalance_dates=[date(2025, 1, 1), date(2025, 1, 3)],
        score_snapshots=_scores(),
        memberships=_memberships(),
        benchmark_ticker="BENCH3",
        policy=policy,
    )

    raw_return = comparison.raw_result.periods[0].asset_returns["TEST3"]
    event_return = comparison.event_aware_result.periods[0].asset_returns["TEST3"]
    assert raw_return == pytest.approx(-0.745)
    assert event_return == pytest.approx(0.02)
    assert comparison.event_aware_result.ending_equity > comparison.raw_result.ending_equity
    assert DIAGNOSTIC_EVENT_AWARE_BACKTEST in comparison.event_aware_result.warnings
    assert not comparison.readiness_promotion_allowed


def test_strict_m15_refuses_latest_state_b3_supplement_history() -> None:
    test, benchmark = _audits()
    dataset = materialize_historical_event_dataset(
        audits=[test, benchmark],
        bars=_bars(),
    )

    assert B3_SUPPLEMENT_HISTORICAL_COMPLETENESS_UNPROVEN in dataset.strict_blockers
    assert not dataset.historical_source_completeness_proven
    assert not dataset.strict_event_aware_backtest_ready
    with pytest.raises(ValueError, match=STRICT_EVENT_AWARE_DATASET_REQUIRED):
        run_event_aware_m15_backtest(
            dataset=dataset,
            rebalance_dates=[date(2025, 1, 1), date(2025, 1, 3)],
            score_snapshots=_scores(),
            memberships=_memberships(),
            benchmark_ticker="BENCH3",
            policy=BacktestPolicy(top_n=1),
        )


def test_adjusted_input_is_rejected_to_prevent_silent_double_adjustment() -> None:
    test, benchmark = _audits()
    bars = _bars()
    bars[0] = _bar(
        "TEST3",
        date(2025, 1, 2),
        40.0,
        open_price=39.0,
        isin="BRTESTACNOR0",
        adjusted_close=10.0,
    )

    with pytest.raises(ValueError, match="raw unadjusted COTAHIST"):
        materialize_historical_event_dataset(
            audits=[test, benchmark],
            bars=bars,
        )


def test_cvm_ipe_corroboration_is_evidence_not_source_completeness_promotion() -> None:
    test, benchmark = _audits()
    test_ledger = audit_cvm_ipe_corporate_action_ledger(
        issuing_company="TEST",
        ticker="TEST3",
        cvm_code=1,
        b3_payload=_split_payload(),
        documents=(),
        source_years=(2025,),
        start_date=START,
        end_date=END,
        generated_at=GENERATED_AT,
    )
    benchmark_ledger = audit_cvm_ipe_corporate_action_ledger(
        issuing_company="BENCH",
        ticker="BENCH3",
        cvm_code=2,
        b3_payload=_empty_payload(),
        documents=(),
        source_years=(2025,),
        start_date=START,
        end_date=END,
        generated_at=GENERATED_AT,
    )
    dataset = materialize_historical_event_dataset(
        audits=[test, benchmark],
        bars=_bars(),
        cvm_ipe_audits=[test_ledger, benchmark_ledger],
    )

    assert dataset.cvm_ipe_observed_event_corroboration_complete is False
    assert CVM_IPE_OBSERVED_EVENT_CORROBORATION_INCOMPLETE in dataset.strict_blockers
    assert not dataset.historical_source_completeness_proven
    assert not dataset.strict_event_aware_backtest_ready
