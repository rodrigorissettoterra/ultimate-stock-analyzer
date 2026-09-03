from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from ultimate_stock_analyzer.backtesting.cvm_fca_applicability_source_audit import (
    audit_fca_historical_applicability_source,
)
from ultimate_stock_analyzer.collectors.cvm import CVMCollector


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit official CVM FCA archives for historical model-applicability evidence."
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

    reports = []
    for year in years:
        source_url = collector.dataset_url("FCA", year)
        archive = collector.download_zip("FCA", year)
        reports.append(
            audit_fca_historical_applicability_source(
                archive_content=archive,
                collected_at=generated_at,
                delivery_year=year,
                source_url=source_url,
                requested_cvm_codes=cvm_codes,
            )
        )

    blockers = sorted({blocker for report in reports for blocker in report.blockers})
    payload = {
        "schema_version": "0.1",
        "effect": "fca_historical_applicability_source_audit_no_routing_change",
        "generated_at": generated_at.isoformat(),
        "delivery_years": list(years),
        "requested_cvm_codes": list(cvm_codes),
        "reports": [report.to_dict() for report in reports],
        "summary": {
            "all_archives_have_issuer_coverage": all(
                report.issuer_coverage_complete for report in reports
            ),
            "any_applicability_fields_found": any(
                report.applicability_fields_found for report in reports
            ),
            "all_archives_have_filing_timing_fields": all(
                report.filing_timing_fields_found for report in reports
            ),
            "deterministic_model_routing_supported": False,
            "sector_routing_point_in_time_ready": False,
            "readiness_promotion_allowed": False,
            "blockers": blockers,
        },
        "warnings": [
            "FCA candidate fields are discovery evidence only; header matches do not prove model-family semantics.",
            "Reference-period and revision metadata are not accepted as publication timing.",
            "No model-family route is promoted until source semantics and mapping rules are separately validated.",
        ],
    }
    args.output.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
        newline="\n",
    )


if __name__ == "__main__":
    main()
