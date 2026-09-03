from __future__ import annotations

import argparse
import json
from collections import defaultdict
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from typing import Any

from ultimate_stock_analyzer.backtesting.b3_event_aware_coverage import (
    audit_b3_event_aware_coverage,
)
from ultimate_stock_analyzer.backtesting.historical_event_dataset import (
    HistoricalEventAwareDataset,
    compare_raw_and_event_aware_m15,
    materialize_historical_event_dataset,
)
from ultimate_stock_analyzer.backtesting.models import (
    BacktestPolicy,
    ScoreSnapshot,
    UniverseMembership,
)
from ultimate_stock_analyzer.collectors.b3_dividends import B3DividendCollector
from ultimate_stock_analyzer.market.prices import B3CotahistCollector, PriceBar


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Materialize validated B3 corporate actions into an M15-compatible historical "
            "dataset while preserving raw COTAHIST and fail-closed source-completeness blockers."
        )
    )
    parser.add_argument(
        "--sample",
        action="append",
        required=True,
        help="Issuing-company/ticker pair in COMPANY:TICKER form; repeat as needed.",
    )
    parser.add_argument("--start-year", type=int, default=2024)
    parser.add_argument("--end-year", type=int, default=2025)
    parser.add_argument(
        "--output",
        default="historical-event-aware-m15-integration.json",
    )
    return parser


def main() -> None:
    args = _parser().parse_args()
    if args.start_year > args.end_year:
        raise SystemExit("start-year must not be after end-year")

    samples = _parse_samples(args.sample)
    generated_at = datetime.now(UTC)
    start_date = date(args.start_year, 1, 1)
    end_date = date(args.end_year, 12, 31)
    supplement = B3DividendCollector()
    prices = B3CotahistCollector()
    payloads = {company: supplement.fetch_payload(company) for company in samples}

    tickers_by_year: dict[int, set[str]] = defaultdict(set)
    for year in range(args.start_year, args.end_year + 1):
        tickers_by_year[year].update(samples.values())
    for company, ticker in samples.items():
        for year in _event_years(
            payloads[company],
            start_date=start_date,
            end_date=end_date,
        ):
            tickers_by_year[year].add(ticker)

    bars: list[PriceBar] = []
    downloaded_years: list[int] = []
    for year, tickers in sorted(tickers_by_year.items()):
        bars.extend(prices.fetch_year(year, tickers=tickers))
        downloaded_years.append(year)

    audits = [
        audit_b3_event_aware_coverage(
            issuing_company=company,
            ticker=ticker,
            payload=payloads[company],
            bars=bars,
            start_date=start_date,
            end_date=end_date,
            generated_at=generated_at,
        )
        for company, ticker in samples.items()
    ]
    dataset = materialize_historical_event_dataset(
        audits=audits,
        bars=bars,
    )
    comparison = _diagnostic_m15_comparison(dataset=dataset, bars=bars)

    report = {
        "schema_version": "0.1",
        "effect": "historical_event_dataset_to_m15_diagnostic_no_readiness_promotion",
        "generated_at": generated_at.isoformat(),
        "start_year": args.start_year,
        "end_year": args.end_year,
        "samples": [
            {"issuing_company": company, "ticker": ticker}
            for company, ticker in samples.items()
        ],
        "price_years_downloaded": downloaded_years,
        "dataset": dataset.to_dict(),
        "diagnostic_m15_comparison": comparison,
        "warnings": [
            "RAW_B3_COTAHIST_IS_FINGERPRINTED_AND_NEVER_OVERWRITTEN",
            "VALIDATED_SHARE_ACTIONS_AND_CASH_DISTRIBUTIONS_ARE_SEPARATE_M15_INPUTS",
            "LATEST_STATE_B3_SUPPLEMENT_DOES_NOT_PROVE_HISTORICAL_EVENT_COMPLETENESS",
            "STRICT_M15_REMAINS_BLOCKED_UNTIL_SOURCE_COMPLETENESS_IS_PROVEN",
            "DIAGNOSTIC_M15_COMPARISON_CANNOT_PROMOTE_M16_WEIGHTS_OR_READINESS",
        ],
    }
    Path(args.output).write_text(
        json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True),
        encoding="utf-8",
    )
    print(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True))


def _diagnostic_m15_comparison(
    *,
    dataset: HistoricalEventAwareDataset,
    bars: list[PriceBar],
) -> dict[str, Any] | None:
    for action in dataset.share_actions:
        ticker_bars = sorted(
            (
                bar
                for bar in bars
                if bar.ticker.upper() == action.ticker
            ),
            key=lambda item: item.trade_date,
        )
        prior = [bar for bar in ticker_bars if bar.trade_date < action.ex_date]
        after = [bar for bar in ticker_bars if bar.trade_date > action.ex_date]
        if not prior or not after:
            continue
        entry_bar = prior[-1]
        decision_date = entry_bar.trade_date - timedelta(days=1)
        exit_decision_date = action.ex_date
        available_at = datetime.combine(decision_date, time.min, tzinfo=UTC)
        comparison = compare_raw_and_event_aware_m15(
            dataset=dataset,
            rebalance_dates=[decision_date, exit_decision_date],
            score_snapshots=[
                ScoreSnapshot(
                    ticker=action.ticker,
                    reference_date=decision_date,
                    available_at=available_at,
                    investment_score=100.0,
                    model_version="diagnostic-corporate-action-integration",
                )
            ],
            memberships=[
                UniverseMembership(
                    ticker=action.ticker,
                    start_date=dataset.start_date,
                    end_date=dataset.end_date,
                )
            ],
            benchmark_ticker=action.ticker,
            policy=BacktestPolicy(
                top_n=1,
                transaction_cost_bps=0.0,
                slippage_bps=0.0,
            ),
        )
        payload = comparison.to_dict()
        payload["ticker"] = action.ticker
        payload["share_action_ex_date"] = action.ex_date.isoformat()
        payload["share_action_ratio_new_per_old"] = action.ratio_new_per_old
        payload["decision_date"] = decision_date.isoformat()
        payload["exit_decision_date"] = exit_decision_date.isoformat()
        payload["raw_asset_return"] = comparison.raw_result.periods[0].asset_returns[action.ticker]
        payload["event_aware_asset_return"] = (
            comparison.event_aware_result.periods[0].asset_returns[action.ticker]
        )
        return payload
    return None


def _parse_samples(values: list[str]) -> dict[str, str]:
    samples: dict[str, str] = {}
    for value in values:
        company, separator, ticker = value.partition(":")
        company = "".join(character for character in company.upper() if character.isalnum())
        ticker = "".join(character for character in ticker.upper() if character.isalnum())
        if separator != ":" or not company or not ticker:
            raise SystemExit(f"invalid sample {value!r}; expected COMPANY:TICKER")
        existing = samples.get(company)
        if existing is not None and existing != ticker:
            raise SystemExit(
                f"company {company} mapped to conflicting tickers {existing}/{ticker}"
            )
        samples[company] = ticker
    return samples


def _event_years(
    payload: dict[str, Any],
    *,
    start_date: date,
    end_date: date,
) -> set[int]:
    years: set[int] = set()
    latest_downloadable_year = datetime.now(UTC).year
    for key in ("stockDividends", "cashDividends", "subscriptions"):
        rows = payload.get(key) or []
        if not isinstance(rows, list):
            raise TypeError(f"B3 {key} must be a list")
        for row in rows:
            if not isinstance(row, dict):
                continue
            event_date = _parse_date(row.get("lastDatePrior"))
            if event_date is None or not start_date <= event_date <= end_date:
                continue
            years.add(event_date.year)
            if event_date.year < latest_downloadable_year:
                years.add(event_date.year + 1)
    return years


def _parse_date(value: Any) -> date | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        parts = text.split("/")
        if len(parts) == 3:
            try:
                day, month, year = (int(part) for part in parts)
                return date(year, month, day)
            except ValueError:
                pass
    return None


if __name__ == "__main__":
    main()
