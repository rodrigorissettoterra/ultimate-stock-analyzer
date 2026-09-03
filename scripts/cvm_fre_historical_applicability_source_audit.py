from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from ultimate_stock_analyzer.backtesting.cvm_fre_applicability_source_audit import (
    audit_fre_historical_applicability_source,
)
from ultimate_stock_analyzer.collectors.cvm import CVMCollector


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Inspect official annual CVM FRE archives for structured evidence that "
            "could support historical model-family applicability."
        )
    )
    parser.add_argument("--year", action="append", type=int, required=True)
    parser.add_argument("--cvm-code", action="append", type=int, required=True)
    parser.add_argument(
        "--output",
        default="cvm-fre-historical-applicability-source-audit.json",
    )
    args = parser.parse_args()

    years = tuple(sorted(set(args.year)))
    cvm_codes = tuple(sorted(set(args.cvm_code)))
    collector = CVMCollector(timeout_seconds=90.0)
    collected_at = datetime.now(UTC)

    reports = []
    for year in years:
        archive = collector.download_zip("FRE", year)
        source_url = collector.dataset_url("FRE", year)
        reports.append(
            audit_fre_historical_applicability_source(
                archive_content=archive,
                collected_at=collected_at,
                delivery_year=year,
                source_url=source_url,
                requested_cvm_codes=cvm_codes,
            )
        )

    payload = {
        "schema_version": "0.1",
        "effect": "fre_historical_applicability_source_audit_no_routing_change",
        "generated_at": collected_at.isoformat(),
        "delivery_years": list(years),
        "requested_cvm_codes": list(cvm_codes),
        "reports": [report.to_dict() for report in reports],
        "summary": {
            "all_archives_have_issuer_coverage": all(
                report.issuer_coverage_complete for report in reports
            ),
            "any_structured_activity_fields_found": any(
                report.structured_activity_fields_found for report in reports
            ),
            "all_archives_have_filing_timing_fields": all(
                report.filing_timing_fields_found for report in reports
            ),
            "deterministic_model_routing_supported": all(
                report.deterministic_model_routing_supported for report in reports
            ),
            "sector_routing_point_in_time_ready": all(
                report.sector_routing_point_in_time_ready for report in reports
            ),
            "readiness_promotion_allowed": False,
            "blockers": sorted(
                {
                    blocker
                    for report in reports
                    for blocker in report.blockers
                }
            ),
        },
        "warnings": [
            (
                "FRE activity-like fields are discovery evidence only; their presence "
                "does not reproduce historical B3 taxonomy."
            ),
            (
                "No model-family mapping is promoted until field semantics, filing "
                "timing, revisions and deterministic routing rules are validated."
            ),
        ],
    }

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
