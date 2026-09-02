from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from ultimate_stock_analyzer.backtesting.b3_event_aware_coverage import (
    B3_SUPPLEMENT_HISTORICAL_COMPLETENESS_UNPROVEN,
    audit_b3_event_aware_coverage,
)
from ultimate_stock_analyzer.collectors.b3_dividends import B3DividendCollector
from ultimate_stock_analyzer.market.prices import B3CotahistCollector, PriceBar


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Audit whether observed B3 corporate actions can safely feed event-aware "
            "historical return paths without changing raw COTAHIST."
        ),
    )
    parser.add_argument(
        "--sample",
        action="append",
        required=True,
        help="Issuing-company/ticker pair in COMPANY:TICKER form; repeat as needed.",
    )
    parser.add_argument("--start-year", type=int, default=2020)
    parser.add_argument("--end-year", type=int, default=2025)
    parser.add_argument(
        "--output",
        default="b3-event-aware-coverage-audit.json",
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

    payloads = {
        company: supplement.fetch_payload(company)
        for company in samples
    }

    tickers_by_year: dict[int, set[str]] = defaultdict(set)
    for company, ticker in samples.items():
        years = _event_years(
            payloads[company],
            start_date=start_date,
            end_date=end_date,
        )
        for year in years:
            tickers_by_year[year].add(ticker)

    bars_by_ticker: dict[str, list[PriceBar]] = defaultdict(list)
    downloaded_years: list[int] = []
    for year, tickers in sorted(tickers_by_year.items()):
        year_bars = prices.fetch_year(year, tickers=tickers)
        downloaded_years.append(year)
        for bar in year_bars:
            bars_by_ticker[bar.ticker.upper()].append(bar)

    audits = []
    for company, ticker in samples.items():
        audit = audit_b3_event_aware_coverage(
            issuing_company=company,
            ticker=ticker,
            payload=payloads[company],
            bars=bars_by_ticker[ticker],
            start_date=start_date,
            end_date=end_date,
            generated_at=generated_at,
        )
        audits.append(audit)

    strict_blockers = sorted(
        {
            blocker
            for audit in audits
            for blocker in audit.strict_blockers
        }
    )
    observed_blockers = sorted(
        {
            blocker
            for audit in audits
            for blocker in audit.observed_blockers
        }
    )
    report = {
        "schema_version": "0.1",
        "effect": "diagnostic_only_event_aware_coverage_no_readiness_change",
        "generated_at": generated_at.isoformat(),
        "start_year": args.start_year,
        "end_year": args.end_year,
        "sample_count": len(audits),
        "samples": [
            {"issuing_company": company, "ticker": ticker}
            for company, ticker in samples.items()
        ],
        "price_years_downloaded": downloaded_years,
        "relevant_stock_event_count": sum(
            audit.relevant_stock_event_count for audit in audits
        ),
        "converted_share_action_count": sum(
            audit.converted_share_action_count for audit in audits
        ),
        "blocked_share_action_count": sum(
            audit.blocked_share_action_count for audit in audits
        ),
        "relevant_cash_event_count": sum(
            audit.relevant_cash_event_count for audit in audits
        ),
        "parsed_relevant_cash_event_count": sum(
            audit.parsed_relevant_cash_event_count for audit in audits
        ),
        "converted_cash_distribution_count": sum(
            audit.converted_cash_distribution_count for audit in audits
        ),
        "blocked_cash_distribution_count": sum(
            audit.blocked_cash_distribution_count for audit in audits
        ),
        "relevant_subscription_count": sum(
            audit.relevant_subscription_count for audit in audits
        ),
        "ambiguous_event_scope_count": sum(
            audit.ambiguous_event_scope_count for audit in audits
        ),
        "observed_complete_sample_count": sum(
            audit.observed_event_coverage_complete for audit in audits
        ),
        "strict_ready_sample_count": sum(
            audit.strict_event_aware_backtest_ready for audit in audits
        ),
        "share_status_counts": dict(
            sorted(
                Counter(
                    item.status
                    for audit in audits
                    for item in audit.share_conversions
                ).items()
            )
        ),
        "cash_status_counts": dict(
            sorted(
                Counter(
                    item.status
                    for audit in audits
                    for item in audit.cash_conversions
                ).items()
            )
        ),
        "observed_blockers": observed_blockers,
        "strict_blockers": strict_blockers,
        "historical_source_completeness_proven": False,
        "strict_event_aware_backtest_ready": False,
        "readiness_promotion_allowed": False,
        "price_adjustment_applied": False,
        "price_series_blocker_removed": False,
        "audits": [audit.to_dict() for audit in audits],
        "warnings": [
            "RAW_B3_COTAHIST_REMAINS_UNADJUSTED",
            "CASH_LAST_DATE_PRIOR_IS_CONVERTED_TO_FIRST_ACTUAL_EX_TRADING_SESSION",
            "OBSERVED_EVENT_CONVERSION_DOES_NOT_PROVE_HISTORICAL_SOURCE_COMPLETENESS",
            "SUBSCRIPTIONS_UNSUPPORTED_STOCK_EVENTS_AND_UNVERIFIED_"
            "SAME_SESSION_ORDERING_FAIL_CLOSED",
            "NO_READINESS_OR_BACKTEST_PROMOTION_IN_THIS_BLOCK",
        ],
    }

    if B3_SUPPLEMENT_HISTORICAL_COMPLETENESS_UNPROVEN not in strict_blockers:
        raise RuntimeError("strict source-completeness blocker must always remain")

    Path(args.output).write_text(
        json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True),
        encoding="utf-8",
    )
    print(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True))


def _parse_samples(values: list[str]) -> dict[str, str]:
    samples: dict[str, str] = {}
    for value in values:
        company, separator, ticker = value.partition(":")
        company = "".join(
            character
            for character in company.upper()
            if character.isalnum()
        )
        ticker = "".join(
            character
            for character in ticker.upper()
            if character.isalnum()
        )
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
    for key in ("stockDividends", "cashDividends", "subscriptions"):
        rows = payload.get(key) or []
        if not isinstance(rows, list):
            raise TypeError(f"B3 {key} must be a list")
        for row in rows:
            if not isinstance(row, dict):
                continue
            event_date = _parse_date(row.get("lastDatePrior"))
            if event_date is not None and start_date <= event_date <= end_date:
                years.add(event_date.year)
    return years


def _parse_date(value: Any) -> date | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text)
    except ValueError:
        pass
    if "T" in text:
        try:
            return date.fromisoformat(text.split("T", 1)[0])
        except ValueError:
            pass
    try:
        return datetime.strptime(text, "%d/%m/%Y").date()
    except ValueError:
        return None


if __name__ == "__main__":
    main()
