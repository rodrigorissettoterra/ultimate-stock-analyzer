from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import UTC, datetime, timedelta
from pathlib import Path

from ultimate_stock_analyzer.backtesting.b3_share_action_conversion import (
    convert_b3_stock_action,
)
from ultimate_stock_analyzer.backtesting.models import PricePoint
from ultimate_stock_analyzer.backtesting.returns import total_holding_return
from ultimate_stock_analyzer.collectors.b3_corporate_actions import (
    B3CorporateActionsContractAuditor,
)
from ultimate_stock_analyzer.market.prices import B3CotahistCollector, PriceBar


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Regress empirically validated B3 ShareAction conversions against raw COTAHIST.",
    )
    parser.add_argument(
        "--sample",
        action="append",
        required=True,
        help="Issuing-company/ticker pair in COMPANY:TICKER form; repeat as needed.",
    )
    parser.add_argument("--output", default="b3-share-action-conversion-regression.json")
    return parser


def main() -> None:
    args = _parser().parse_args()
    samples = _parse_samples(args.sample)
    generated_at = datetime.now(UTC)
    auditor = B3CorporateActionsContractAuditor.default()
    price_collector = B3CotahistCollector()

    audits = {company: auditor.audit(company) for company in samples}
    supported_events = {
        company: [
            event
            for event in audit.stock_actions
            if event.supported_label
            and event.factor is not None
            and event.last_date_prior is not None
        ]
        for company, audit in audits.items()
    }

    tickers_by_year: dict[int, set[str]] = defaultdict(set)
    for company, events in supported_events.items():
        ticker = samples[company]
        for event in events:
            assert event.last_date_prior is not None
            tickers_by_year[event.last_date_prior.year].add(ticker)

    bars_by_ticker: dict[str, list[PriceBar]] = defaultdict(list)
    price_years: list[int] = []
    for year, tickers in sorted(tickers_by_year.items()):
        bars = price_collector.fetch_year(year, tickers=tickers)
        price_years.append(year)
        for bar in bars:
            bars_by_ticker[bar.ticker.upper()].append(bar)

    conversions = []
    economic_regressions = []
    for company, events in supported_events.items():
        ticker = samples[company]
        ticker_bars = bars_by_ticker[ticker]
        for event in events:
            conversion = convert_b3_stock_action(
                issuing_company=company,
                ticker=ticker,
                event=event,
                bars=ticker_bars,
            )
            conversions.append(conversion)
            if conversion.action is None or conversion.evidence is None:
                continue
            evidence = conversion.evidence
            if evidence.pre_close is None or evidence.post_close is None:
                continue

            prices = [
                PricePoint(
                    ticker=ticker,
                    trading_date=event.last_date_prior,
                    close=evidence.pre_close,
                ),
                PricePoint(
                    ticker=ticker,
                    trading_date=conversion.action.ex_date,
                    close=evidence.post_close,
                ),
            ]
            assert event.last_date_prior is not None
            raw_return = total_holding_return(
                ticker=ticker,
                entry_decision_date=event.last_date_prior - timedelta(days=1),
                exit_decision_date=event.last_date_prior,
                prices=prices,
            )
            event_aware_return = total_holding_return(
                ticker=ticker,
                entry_decision_date=event.last_date_prior - timedelta(days=1),
                exit_decision_date=event.last_date_prior,
                prices=prices,
                share_actions=[conversion.action],
            )
            if raw_return is None or event_aware_return is None:
                continue
            economic_regressions.append(
                {
                    "issuing_company": company,
                    "ticker": ticker,
                    "label": event.normalized_label,
                    "factor": event.factor,
                    "com_date": event.last_date_prior.isoformat(),
                    "ex_date": conversion.action.ex_date.isoformat(),
                    "ratio_new_per_old": conversion.action.ratio_new_per_old,
                    "raw_price_only_return": raw_return,
                    "event_aware_return": event_aware_return,
                    "absolute_return_improved": abs(event_aware_return) < abs(raw_return),
                    "absolute_raw_return": abs(raw_return),
                    "absolute_event_aware_return": abs(event_aware_return),
                }
            )

    converted = [item for item in conversions if item.converted]
    converted_by_label = Counter(item.label for item in converted)
    converted_issuers_by_label: dict[str, set[str]] = defaultdict(set)
    for item in converted:
        if item.evidence is not None:
            converted_issuers_by_label[item.label].add(item.evidence.issuing_company)

    report = {
        "schema_version": "0.1",
        "effect": "share_action_conversion_contract_only_no_readiness_promotion",
        "generated_at": generated_at.isoformat().replace("+00:00", "Z"),
        "samples": [
            {"issuing_company": company, "ticker": ticker}
            for company, ticker in sorted(samples.items())
        ],
        "price_source": "B3_COTAHIST_RAW",
        "price_years": price_years,
        "conversion_contract": {
            "BONIFICACAO": "1 + factor/100",
            "DESDOBRAMENTO": "1 + factor/100",
            "GRUPAMENTO": "factor",
        },
        "conversion_attempt_count": len(conversions),
        "converted_event_count": len(converted),
        "blocked_event_count": len(conversions) - len(converted),
        "converted_event_count_by_label": dict(sorted(converted_by_label.items())),
        "converted_issuer_count_by_label": {
            label: len(issuers)
            for label, issuers in sorted(converted_issuers_by_label.items())
        },
        "conversions": [item.to_dict() for item in conversions],
        "economic_regression_count": len(economic_regressions),
        "economic_regression_improved_count": sum(
            item["absolute_return_improved"] for item in economic_regressions
        ),
        "economic_regressions": economic_regressions,
        "max_absolute_event_aware_return": max(
            (item["absolute_event_aware_return"] for item in economic_regressions),
            default=None,
        ),
        "share_action_conversion_available": True,
        "price_adjustment_applied": False,
        "historical_backtest_readiness_changed": False,
        "price_series_blocker_removed": False,
        "warnings": [
            "CONVERSION_REQUIRES_EVENT_LEVEL_B3_COTAHIST_IDENTITY_AND_FACTOR_EVIDENCE",
            "SUBSCRIPTIONS_AND_UNSUPPORTED_STOCK_EVENTS_REMAIN_FAIL_CLOSED",
            "PRICE_SERIES_UNADJUSTED_FOR_CORPORATE_ACTIONS_BLOCKER_REMAINS_UNCHANGED",
            "THIS_BLOCK_DOES_NOT_RUN_OR_PROMOTE_FULL_HISTORICAL_PORTFOLIO_BACKTESTS",
        ],
    }

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))


def _parse_samples(raw_samples: list[str]) -> dict[str, str]:
    samples: dict[str, str] = {}
    for raw_sample in raw_samples:
        company, separator, ticker = raw_sample.partition(":")
        company = company.strip().upper()
        ticker = ticker.strip().upper()
        if separator != ":" or not company or not ticker:
            raise ValueError("samples must use COMPANY:TICKER format")
        if company in samples and samples[company] != ticker:
            raise ValueError(f"multiple tickers provided for issuing company {company}")
        samples[company] = ticker
    return samples


if __name__ == "__main__":
    main()
