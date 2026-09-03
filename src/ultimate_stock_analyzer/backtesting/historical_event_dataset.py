from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date
from typing import Any

from ultimate_stock_analyzer.backtesting.b3_event_aware_coverage import (
    B3_SUPPLEMENT_HISTORICAL_COMPLETENESS_UNPROVEN,
    B3EventAwareCoverageAudit,
)
from ultimate_stock_analyzer.backtesting.cvm_ipe_corporate_action_ledger import (
    CVMIPECorporateActionLedgerAudit,
)
from ultimate_stock_analyzer.backtesting.models import (
    BacktestPolicy,
    BacktestResult,
    CashDistribution,
    PricePoint,
    ScoreSnapshot,
    ShareAction,
    UniverseMembership,
)
from ultimate_stock_analyzer.backtesting.portfolio import run_rebalance_backtest
from ultimate_stock_analyzer.backtesting.raw_price_provenance import raw_price_fingerprint
from ultimate_stock_analyzer.market.prices import PriceBar

CORPORATE_ACTION_DATASET_OBSERVED_COVERAGE_INCOMPLETE = (
    "CORPORATE_ACTION_DATASET_OBSERVED_COVERAGE_INCOMPLETE"
)
CORPORATE_ACTION_DATASET_SOURCE_COMPLETENESS_UNPROVEN = (
    "CORPORATE_ACTION_DATASET_SOURCE_COMPLETENESS_UNPROVEN"
)
CVM_IPE_OBSERVED_EVENT_CORROBORATION_INCOMPLETE = (
    "CVM_IPE_OBSERVED_EVENT_CORROBORATION_INCOMPLETE"
)
STRICT_EVENT_AWARE_DATASET_REQUIRED = "STRICT_EVENT_AWARE_DATASET_REQUIRED"
DIAGNOSTIC_EVENT_AWARE_BACKTEST = "DIAGNOSTIC_EVENT_AWARE_BACKTEST"


@dataclass(frozen=True, slots=True)
class HistoricalEventAwareDataset:
    start_date: date
    end_date: date
    tickers: tuple[str, ...]
    prices: tuple[PricePoint, ...]
    share_actions: tuple[ShareAction, ...]
    distributions: tuple[CashDistribution, ...]
    raw_price_bar_count: int
    raw_price_fingerprint_sha256: str
    observed_blockers: tuple[str, ...]
    strict_blockers: tuple[str, ...]
    observed_event_path_ready: bool
    historical_source_completeness_proven: bool
    cvm_ipe_observed_event_corroboration_complete: bool | None
    strict_event_aware_backtest_ready: bool
    raw_price_series_preserved: bool = True
    price_adjustment_applied: bool = False
    price_series_blocker_removed: bool = False
    readiness_promotion_allowed: bool = False
    effect: str = "historical_event_dataset_materialized_no_readiness_promotion"
    schema_version: str = "0.1"

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "effect": self.effect,
            "start_date": self.start_date.isoformat(),
            "end_date": self.end_date.isoformat(),
            "tickers": list(self.tickers),
            "price_count": len(self.prices),
            "share_action_count": len(self.share_actions),
            "distribution_count": len(self.distributions),
            "raw_price_bar_count": self.raw_price_bar_count,
            "raw_price_fingerprint_sha256": self.raw_price_fingerprint_sha256,
            "observed_blockers": list(self.observed_blockers),
            "strict_blockers": list(self.strict_blockers),
            "observed_event_path_ready": self.observed_event_path_ready,
            "historical_source_completeness_proven": (
                self.historical_source_completeness_proven
            ),
            "cvm_ipe_observed_event_corroboration_complete": (
                self.cvm_ipe_observed_event_corroboration_complete
            ),
            "strict_event_aware_backtest_ready": self.strict_event_aware_backtest_ready,
            "raw_price_series_preserved": self.raw_price_series_preserved,
            "price_adjustment_applied": self.price_adjustment_applied,
            "price_series_blocker_removed": self.price_series_blocker_removed,
            "readiness_promotion_allowed": self.readiness_promotion_allowed,
            "share_actions": [
                {
                    "ticker": item.ticker,
                    "ex_date": item.ex_date.isoformat(),
                    "ratio_new_per_old": item.ratio_new_per_old,
                }
                for item in self.share_actions
            ],
            "distributions": [
                {
                    "ticker": item.ticker,
                    "ex_date": item.ex_date.isoformat(),
                    "amount_per_share": item.amount_per_share,
                }
                for item in self.distributions
            ],
        }


@dataclass(frozen=True, slots=True)
class M15EventAwareComparison:
    raw_result: BacktestResult
    event_aware_result: BacktestResult
    ending_equity_delta: float
    diagnostic_only: bool = True
    readiness_promotion_allowed: bool = False
    effect: str = "diagnostic_raw_vs_event_aware_m15_comparison"

    def to_dict(self) -> dict[str, Any]:
        return {
            "effect": self.effect,
            "raw_ending_equity": self.raw_result.ending_equity,
            "event_aware_ending_equity": self.event_aware_result.ending_equity,
            "ending_equity_delta": self.ending_equity_delta,
            "raw_periods": len(self.raw_result.periods),
            "event_aware_periods": len(self.event_aware_result.periods),
            "event_aware_warnings": list(self.event_aware_result.warnings),
            "diagnostic_only": self.diagnostic_only,
            "readiness_promotion_allowed": self.readiness_promotion_allowed,
        }


def materialize_historical_event_dataset(
    *,
    audits: list[B3EventAwareCoverageAudit] | tuple[B3EventAwareCoverageAudit, ...],
    bars: list[PriceBar] | tuple[PriceBar, ...],
    cvm_ipe_audits: (
        list[CVMIPECorporateActionLedgerAudit]
        | tuple[CVMIPECorporateActionLedgerAudit, ...]
        | None
    ) = None,
) -> HistoricalEventAwareDataset:
    if not audits:
        raise ValueError("at least one event-aware coverage audit is required")

    ordered_audits = tuple(sorted(audits, key=lambda item: item.ticker))
    start_date = ordered_audits[0].start_date
    end_date = ordered_audits[0].end_date
    tickers = tuple(item.ticker.upper() for item in ordered_audits)
    if len(set(tickers)) != len(tickers):
        raise ValueError("event-aware coverage audits must have unique tickers")
    if any(
        item.start_date != start_date or item.end_date != end_date
        for item in ordered_audits
    ):
        raise ValueError("event-aware coverage audits must use one common date window")

    target_bars = tuple(
        sorted(
            (
                bar
                for bar in bars
                if bar.ticker.upper() in tickers
                and start_date <= bar.trade_date <= end_date
            ),
            key=lambda item: (item.trade_date, item.ticker.upper()),
        )
    )
    if not target_bars:
        raise ValueError("historical event dataset has no target COTAHIST bars")
    if any(bar.adjusted_close is not None for bar in target_bars):
        raise ValueError("historical event dataset requires raw unadjusted COTAHIST bars")
    present_tickers = {bar.ticker.upper() for bar in target_bars}
    missing_tickers = sorted(set(tickers) - present_tickers)
    if missing_tickers:
        raise ValueError(f"historical event dataset is missing price bars for {missing_tickers}")

    share_actions = tuple(
        sorted(
            (
                conversion.action
                for audit in ordered_audits
                for conversion in audit.share_conversions
                if (
                    conversion.converted
                    and conversion.action is not None
                    and start_date <= conversion.action.ex_date <= end_date
                )
            ),
            key=lambda item: (item.ex_date, item.ticker),
        )
    )
    distributions = tuple(
        sorted(
            (
                conversion.distribution
                for audit in ordered_audits
                for conversion in audit.cash_conversions
                if (
                    conversion.converted
                    and conversion.distribution is not None
                    and start_date <= conversion.distribution.ex_date <= end_date
                )
            ),
            key=lambda item: (item.ex_date, item.ticker, item.amount_per_share),
        )
    )
    prices = tuple(
        PricePoint(
            ticker=bar.ticker.upper(),
            trading_date=bar.trade_date,
            close=bar.close,
        )
        for bar in target_bars
    )

    observed_blockers = {
        blocker
        for audit in ordered_audits
        for blocker in audit.observed_blockers
    }
    strict_blockers = {
        blocker
        for audit in ordered_audits
        for blocker in audit.strict_blockers
    }
    observed_ready = all(item.observed_event_coverage_complete for item in ordered_audits)
    source_complete = all(item.historical_source_completeness_proven for item in ordered_audits)
    if not observed_ready:
        strict_blockers.add(CORPORATE_ACTION_DATASET_OBSERVED_COVERAGE_INCOMPLETE)
    if not source_complete:
        strict_blockers.add(CORPORATE_ACTION_DATASET_SOURCE_COMPLETENESS_UNPROVEN)
        strict_blockers.add(B3_SUPPLEMENT_HISTORICAL_COMPLETENESS_UNPROVEN)

    cvm_status = _cvm_ipe_corroboration_status(
        tickers=tickers,
        start_date=start_date,
        end_date=end_date,
        audits=cvm_ipe_audits,
    )
    if cvm_status is False:
        strict_blockers.add(CVM_IPE_OBSERVED_EVENT_CORROBORATION_INCOMPLETE)

    strict_ready = (
        observed_ready
        and source_complete
        and all(item.strict_event_aware_backtest_ready for item in ordered_audits)
    )
    return HistoricalEventAwareDataset(
        start_date=start_date,
        end_date=end_date,
        tickers=tickers,
        prices=prices,
        share_actions=share_actions,
        distributions=distributions,
        raw_price_bar_count=len(target_bars),
        raw_price_fingerprint_sha256=raw_price_fingerprint(target_bars),
        observed_blockers=tuple(sorted(observed_blockers)),
        strict_blockers=tuple(sorted(strict_blockers)),
        observed_event_path_ready=observed_ready,
        historical_source_completeness_proven=source_complete,
        cvm_ipe_observed_event_corroboration_complete=cvm_status,
        strict_event_aware_backtest_ready=strict_ready,
    )


def run_event_aware_m15_backtest(
    *,
    dataset: HistoricalEventAwareDataset,
    rebalance_dates: list[date],
    score_snapshots: list[ScoreSnapshot],
    memberships: list[UniverseMembership],
    benchmark_ticker: str,
    policy: BacktestPolicy,
    require_strict: bool = True,
) -> BacktestResult:
    if require_strict and not dataset.strict_event_aware_backtest_ready:
        blockers = ",".join(dataset.strict_blockers)
        raise ValueError(f"{STRICT_EVENT_AWARE_DATASET_REQUIRED}: {blockers}")

    result = run_rebalance_backtest(
        rebalance_dates=rebalance_dates,
        score_snapshots=score_snapshots,
        memberships=memberships,
        prices=list(dataset.prices),
        benchmark_ticker=benchmark_ticker,
        policy=policy,
        share_actions=list(dataset.share_actions),
        distributions=list(dataset.distributions),
    )
    if require_strict:
        return result

    warnings = set(result.warnings)
    warnings.add(DIAGNOSTIC_EVENT_AWARE_BACKTEST)
    warnings.update(dataset.strict_blockers)
    return replace(result, warnings=tuple(sorted(warnings)))


def compare_raw_and_event_aware_m15(
    *,
    dataset: HistoricalEventAwareDataset,
    rebalance_dates: list[date],
    score_snapshots: list[ScoreSnapshot],
    memberships: list[UniverseMembership],
    benchmark_ticker: str,
    policy: BacktestPolicy,
) -> M15EventAwareComparison:
    raw_result = run_rebalance_backtest(
        rebalance_dates=rebalance_dates,
        score_snapshots=score_snapshots,
        memberships=memberships,
        prices=list(dataset.prices),
        benchmark_ticker=benchmark_ticker,
        policy=policy,
    )
    event_aware_result = run_event_aware_m15_backtest(
        dataset=dataset,
        rebalance_dates=rebalance_dates,
        score_snapshots=score_snapshots,
        memberships=memberships,
        benchmark_ticker=benchmark_ticker,
        policy=policy,
        require_strict=False,
    )
    return M15EventAwareComparison(
        raw_result=raw_result,
        event_aware_result=event_aware_result,
        ending_equity_delta=event_aware_result.ending_equity - raw_result.ending_equity,
    )


def _cvm_ipe_corroboration_status(
    *,
    tickers: tuple[str, ...],
    start_date: date,
    end_date: date,
    audits: (
        list[CVMIPECorporateActionLedgerAudit]
        | tuple[CVMIPECorporateActionLedgerAudit, ...]
        | None
    ),
) -> bool | None:
    if audits is None:
        return None
    by_ticker = {item.ticker.upper(): item for item in audits}
    if len(by_ticker) != len(audits):
        raise ValueError("CVM IPE corporate-action audits must have unique tickers")
    unexpected = sorted(set(by_ticker) - set(tickers))
    if unexpected:
        raise ValueError(f"CVM IPE audit ticker is outside event dataset: {unexpected}")
    for ticker, audit in by_ticker.items():
        if audit.start_date != start_date or audit.end_date != end_date:
            raise ValueError(f"CVM IPE audit window mismatch for {ticker}")
    if set(by_ticker) != set(tickers):
        return False
    return all(
        item.observed_event_count == 0
        or item.observed_event_document_corroboration_complete
        for item in audits
    )
