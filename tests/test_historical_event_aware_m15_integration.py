from datetime import date

import pytest

from ultimate_stock_analyzer.backtesting.historical_event_dataset import (
    DIAGNOSTIC_EVENT_AWARE_BACKTEST,
    HistoricalEventAwareDataset,
)
from ultimate_stock_analyzer.backtesting.historical_event_diagnostics import (
    diagnostic_m15_comparison,
)
from ultimate_stock_analyzer.backtesting.models import (
    CashDistribution,
    PricePoint,
    ShareAction,
)

START = date(2025, 1, 1)
END = date(2025, 12, 31)


def _dataset(
    *,
    share_actions: tuple[ShareAction, ...] = (),
    distributions: tuple[CashDistribution, ...] = (),
) -> HistoricalEventAwareDataset:
    return HistoricalEventAwareDataset(
        start_date=START,
        end_date=END,
        tickers=("TEST3",),
        prices=(
            PricePoint(ticker="TEST3", trading_date=date(2025, 1, 2), close=10.0),
            PricePoint(ticker="TEST3", trading_date=date(2025, 1, 3), close=9.0),
            PricePoint(ticker="TEST3", trading_date=date(2025, 1, 6), close=9.2),
        ),
        share_actions=share_actions,
        distributions=distributions,
        raw_price_bar_count=3,
        raw_price_fingerprint_sha256="0" * 64,
        observed_blockers=(),
        strict_blockers=("CORPORATE_ACTION_DATASET_SOURCE_COMPLETENESS_UNPROVEN",),
        observed_event_path_ready=True,
        historical_source_completeness_proven=False,
        cvm_ipe_observed_event_corroboration_complete=None,
        strict_event_aware_backtest_ready=False,
    )


def test_diagnostic_uses_positive_cash_distribution_when_no_share_action_exists() -> None:
    dataset = _dataset(
        distributions=(
            CashDistribution(
                ticker="TEST3",
                ex_date=date(2025, 1, 3),
                amount_per_share=1.0,
            ),
        )
    )

    payload = diagnostic_m15_comparison(dataset=dataset)

    assert payload is not None
    assert payload["event_kind"] == "cash_distribution"
    assert payload["cash_distribution_ex_date"] == "2025-01-03"
    assert payload["cash_distribution_amount_per_share"] == pytest.approx(1.0)
    assert payload["raw_asset_return"] == pytest.approx(-0.08)
    assert payload["event_aware_asset_return"] == pytest.approx(0.02)
    assert payload["diagnostic_only"] is True
    assert payload["readiness_promotion_allowed"] is False
    assert DIAGNOSTIC_EVENT_AWARE_BACKTEST in payload["event_aware_warnings"]


def test_diagnostic_preserves_share_action_path_and_explicit_event_kind() -> None:
    dataset = _dataset(
        share_actions=(
            ShareAction(
                ticker="TEST3",
                ex_date=date(2025, 1, 3),
                ratio_new_per_old=2.0,
            ),
        ),
        distributions=(
            CashDistribution(
                ticker="TEST3",
                ex_date=date(2025, 1, 3),
                amount_per_share=1.0,
            ),
        ),
    )

    payload = diagnostic_m15_comparison(dataset=dataset)

    assert payload is not None
    assert payload["event_kind"] == "share_action"
    assert payload["share_action_ex_date"] == "2025-01-03"
    assert payload["share_action_ratio_new_per_old"] == pytest.approx(2.0)
    assert payload["raw_asset_return"] != payload["event_aware_asset_return"]


def test_zero_value_distribution_does_not_validate_m15_path() -> None:
    dataset = _dataset(
        distributions=(
            CashDistribution(
                ticker="TEST3",
                ex_date=date(2025, 1, 3),
                amount_per_share=0.0,
            ),
        )
    )

    assert diagnostic_m15_comparison(dataset=dataset) is None
