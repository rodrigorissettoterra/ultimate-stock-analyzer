from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from ultimate_stock_analyzer.backtesting.cvm_fca_applicability_filing_ledger import (
    build_fca_applicability_filing_ledger,
)
from ultimate_stock_analyzer.collectors.cvm import CVMCollector


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Bind FCA applicability rows to exact root filing receipt dates."
    )
    parser.add_argument("--year", action="append", type=int, required=True)
    parser.add_argument("--cvm-code", action="append", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    years = tuple(sorted(set(args.year)))
    cvm_codes = tuple(sorted(set(args.cvm_code)))
    collector = CVMCollector()
    generated_at = datetime.now(UTC)
    ledgers = []
    for year in years:
        source_url = collector.dataset_url("FCA", year)
        archive = collector.download_zip("FCA", year)
        ledgers.append(
            build_fca_applicability_filing_ledger(
                archive_content=archive,
                collected_at=generated_at,
                delivery_year=year,
                source_url=source_url,
                requested_cvm_codes=cvm_codes,
            )
        )

    payload = {
        "schema_version": "0.2",
        "effect": "fca_applicability_filing_ledger_no_readiness_promotion",
        "generated_at": generated_at.isoformat(),
        "delivery_years": list(years),
        "requested_cvm_codes": list(cvm_codes),
        "ledgers": [ledger.to_dict() for ledger in ledgers],
        "summary": {
            "filing_count": sum(len(ledger.filings) for ledger in ledgers),
            "all_detail_rows_exactly_materialized": all(
                len(ledger.filings) == ledger.applicability_detail_count
                for ledger in ledgers
            ),
            "all_requested_issuers_have_detail": all(
                not ledger.missing_applicability_detail_codes for ledger in ledgers
            ),
            "all_ledgers_blocker_free": all(not ledger.blockers for ledger in ledgers),
            "readiness_promotion_allowed": False,
        },
        "warnings": [
            "Only applicability detail revisions present in the current annual FCA archive are materialized.",
            "Every accepted detail/root join must match document, version, issuer identity and reference date.",
            "Each materialized filing is admissible only from its own conservative next-day available_from.",
            "Missing issuers or older detail revisions are not inferred and no readiness/model route is promoted here.",
        ],
    }
    args.output.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
        newline="\n",
    )


if __name__ == "__main__":
    main()
