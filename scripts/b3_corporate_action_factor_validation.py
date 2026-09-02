from __future__ import annotations

import argparse
import json
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

from ultimate_stock_analyzer.backtesting.corporate_action_factor_validation import (
    EVENT_ISIN_MISMATCH,
    summarize_factor_evidence,
    validate_corporate_action_factor,
)
from ultimate_stock_analyzer.collectors.b3_corporate_actions import (
    B3CorporateActionsContractAuditor,
)
from ultimate_stock_analyzer.market.prices import B3CotahistCollector, PriceBar


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate B3 corporate-action factor semantics against raw COTAHIST gaps.",
    )
    parser.add_argument(
        "--sample",
        action="append",
        required=True,
        help="Issuing-company/ticker pair in COMPANY:TICKER form; repeat as needed.",
    )
    parser.add_argument("--output", default="b3-factor-cotahist-validation.json")
    return parser


def main() -> None:
    args = _parser().parse_args()
    samples = _parse_samples(args.sample)
    generated_at = datetime.now(UTC)
    action_auditor = B3CorporateActionsContractAuditor.default()
    price_collector = B3CotahistCollector()

    audits = {company: action_auditor.audit(company) for company in samples}
    events_by_company = {
        company: [
            event
            for event in audit.stock_actions
            if event.supported_label and event.factor is not None and event.last_date_prior is not None
        ]
        for company, audit in audits.items()
    }

    tickers_by_year: dict[int, set[str]] = defaultdict(set)
    for company, events in events_by_company.items():
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

    evidence = []
    for company, events in events_by_company.items():
        ticker = samples[company]
        for event in events:
            evidence.append(
                validate_corporate_action_factor(
                    issuing_company=company,
                    ticker=ticker,
                    event=event,
                    bars=bars_by_ticker[ticker],
                )
            )

    summaries = summarize_factor_evidence(evidence)
    supported_labels = sorted({item.label for item in evidence})
    labels_with_price_evidence = sorted(
        {
            item.label
            for item in evidence
            if item.pre_close is not None and item.post_open is not None
        }
    )
    identity_matched = [item for item in evidence if EVENT_ISIN_MISMATCH not in item.blockers]
    all_bars = [bar for bars in bars_by_ticker.values() for bar in bars]

    report = {
        "schema_version": "0.1",
        "effect": "diagnostic_only_no_share_action_or_price_adjustment_promotion",
        "generated_at": generated_at.isoformat().replace("+00:00", "Z"),
        "samples": [
            {"issuing_company": company, "ticker": ticker}
            for company, ticker in sorted(samples.items())
        ],
        "price_source": "B3_COTAHIST",
        "price_years": price_years,
        "raw_price_bar_count": len(all_bars),
        "adjusted_price_bar_count": sum(bar.is_adjusted for bar in all_bars),
        "supported_labels_observed": supported_labels,
        "labels_with_price_evidence": labels_with_price_evidence,
        "evaluated_event_count": len(evidence),
        "identity_matched_event_count": len(identity_matched),
        "empirically_consistent_event_count": sum(
            item.empirically_consistent for item in identity_matched
        ),
        "events": [item.to_dict() for item in evidence],
        "label_summaries": [summary.to_dict() for summary in summaries],
        "promotion_policy": {
            "min_events_per_label": 2,
            "min_issuers_per_label": 2,
            "max_open_relative_error": 0.15,
            "min_second_best_error_margin": 0.10,
        },
        "share_action_conversion_applied": False,
        "price_adjustment_applied": False,
        "factor_formula_promotion_applied": False,
        "strict_backtest_price_readiness_changed": False,
        "warnings": [
            "CLOSE_TO_NEXT_OPEN_RATIO_CONTAINS_NORMAL_OVERNIGHT_MARKET_MOVEMENT",
            "EMPIRICAL_MATCH_DOES_NOT_BY_ITSELF_AUTHORIZE_SHARE_ACTION_CONVERSION",
            "SUBSCRIPTION_RIGHTS_REMAIN_OUTSIDE_THIS_FACTOR_VALIDATION",
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
    if not samples:
        raise ValueError("at least one sample is required")
    return samples


if __name__ == "__main__":
    main()
