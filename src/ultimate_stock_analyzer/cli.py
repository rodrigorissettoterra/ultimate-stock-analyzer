from __future__ import annotations

import argparse
from datetime import UTC, datetime

from ultimate_stock_analyzer.bootstrap import (
    BootstrapDataset,
    FundamentalCoverageProfiler,
    PublicDataBootstrapPlan,
    PublicDataBootstrapService,
)
from ultimate_stock_analyzer.orchestration.fundamentus_screen import (
    screen_regular_dividend_payers,
)


def main() -> None:
    parser = argparse.ArgumentParser(prog="ultimate-stock-analyzer")
    sub = parser.add_subparsers(dest="command", required=True)

    scan = sub.add_parser(
        "screen-dividends",
        help="Screen regular dividend/JCP payers using free Fundamentus fallback data",
    )
    scan.add_argument(
        "--min-dy",
        type=float,
        default=0.0,
        help="Minimum snapshot DY as decimal, e.g. 0.05",
    )
    scan.add_argument(
        "--min-liquidity",
        type=float,
        default=1_000_000.0,
        help="Minimum 2-month liquidity",
    )
    scan.add_argument("--max-candidates", type=int, default=50)

    bootstrap = sub.add_parser(
        "bootstrap-public-data",
        help="Materialize official CVM/B3 historical inputs and an auditable manifest",
    )
    bootstrap.add_argument("--start-year", type=int, required=True)
    bootstrap.add_argument("--end-year", type=int, required=True)
    bootstrap.add_argument(
        "--ticker",
        action="append",
        default=[],
        help="Optional ticker filter; repeat for multiple tickers. Omit for full universe.",
    )
    bootstrap.add_argument("--data-dir", default="./data")

    coverage = sub.add_parser(
        "profile-coverage",
        help="Profile accounting and publication-timestamp coverage of one bootstrap run",
    )
    coverage.add_argument("--run-dir", required=True)
    coverage.add_argument("--data-dir", default="./data")

    args = parser.parse_args()
    if args.command == "screen-dividends":
        rows = screen_regular_dividend_payers(
            as_of=datetime.now(UTC).date(),
            min_snapshot_dy=args.min_dy,
            min_liquidity_2m=args.min_liquidity,
            max_candidates=args.max_candidates,
        )
        for row in rows:
            print(
                f"{row.ticker:8} regularity={row.regularity_score:5.1f} "
                f"DY={row.dy_snapshot * 100:5.2f}% price={row.current_price:8.2f} "
                f"years={row.years_paid} gap={row.max_gap_months}"
            )
        return

    if args.command == "bootstrap-public-data":
        plan = PublicDataBootstrapPlan(
            start_year=args.start_year,
            end_year=args.end_year,
            tickers=tuple(args.ticker),
        )
        manifest = PublicDataBootstrapService(args.data_dir).run(plan)
        print(
            f"bootstrap={manifest.status} run_id={manifest.run_id} "
            f"issuers={manifest.counts.get('issuers', 0)} "
            f"securities={manifest.counts.get('securities', 0)} "
            f"statement_lines={manifest.counts.get('financial_statement_lines', 0)} "
            f"price_bars={manifest.counts.get('price_bars', 0)}"
        )
        return

    if args.command == "profile-coverage":
        dataset = BootstrapDataset(args.run_dir)
        summary = FundamentalCoverageProfiler(dataset).write(
            args.data_dir,
            generated_at=datetime.now(UTC),
        )
        print(
            f"coverage run_id={summary.bootstrap_run_id} companies={summary.companies} "
            f"company_years={summary.company_years} "
            f"critical_complete={summary.critical_complete_company_years} "
            f"pit_complete={summary.point_in_time_critical_complete_company_years} "
            f"longitudinal_ready={summary.longitudinal_pair_ready_company_years}"
        )


if __name__ == "__main__":
    main()
