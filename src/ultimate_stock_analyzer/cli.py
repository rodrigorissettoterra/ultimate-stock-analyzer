from __future__ import annotations

import argparse
from datetime import date

from ultimate_stock_analyzer.orchestration.fundamentus_screen import screen_regular_dividend_payers


def main() -> None:
    parser = argparse.ArgumentParser(prog="ultimate-stock-analyzer")
    sub = parser.add_subparsers(dest="command", required=True)

    scan = sub.add_parser("screen-dividends", help="Screen regular dividend/JCP payers using free Fundamentus fallback data")
    scan.add_argument("--min-dy", type=float, default=0.0, help="Minimum snapshot DY as decimal, e.g. 0.05")
    scan.add_argument("--min-liquidity", type=float, default=1_000_000.0, help="Minimum 2-month liquidity")
    scan.add_argument("--max-candidates", type=int, default=50)

    args = parser.parse_args()
    if args.command == "screen-dividends":
        rows = screen_regular_dividend_payers(
            as_of=date.today(),
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


if __name__ == "__main__":
    main()
