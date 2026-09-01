from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from ultimate_stock_analyzer.collectors.cvm import CVMCollector
from ultimate_stock_analyzer.collectors.cvm_targeted_statements import (
    load_company_statements_from_archive,
)
from ultimate_stock_analyzer.scoring.itsa_holding_schema_stability import (
    ITSA_BASELINE_YEAR,
    ITSA_COMPANY_ID,
    ITSA_CVM_CODE,
    audit_itsa_holding_schema_stability,
)
from ultimate_stock_analyzer.scoring.statement_schema_stability import (
    STATUS_STABLE_EXACT,
)
from ultimate_stock_analyzer.scoring.statement_tree_audit import (
    audit_financial_statement_tree,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Audit ITSA exact holding-account schema stability across annual CVM DFPs."
        )
    )
    parser.add_argument("--start-year", type=int, default=2021)
    parser.add_argument("--end-year", type=int, default=2025)
    parser.add_argument("--baseline-year", type=int, default=ITSA_BASELINE_YEAR)
    parser.add_argument(
        "--output",
        default="itsa-holding-schema-stability-audit.json",
    )
    args = parser.parse_args()

    if args.start_year > args.end_year:
        raise ValueError("start-year must not be greater than end-year")
    if args.baseline_year < args.start_year or args.baseline_year > args.end_year:
        raise ValueError("baseline-year must be inside the requested audit window")

    collected_at = datetime.now(UTC)
    collector = CVMCollector()
    reports_by_year = {}
    year_reference_dates: dict[str, str | None] = {}
    year_line_counts: dict[str, int] = {}

    for year in range(args.start_year, args.end_year + 1):
        archive = collector.download_zip("DFP", year)
        lines = load_company_statements_from_archive(
            archive,
            cvm_code=ITSA_CVM_CODE,
            document_type="DFP",
            statements=("BPA", "BPP", "DRE"),
            scope_token="ind",
            collected_at=collected_at,
            collector=collector,
        )
        report = audit_financial_statement_tree(
            lines,
            company_id=ITSA_COMPANY_ID,
            max_depth=6,
        )
        reports_by_year[year] = report
        year_reference_dates[str(year)] = (
            report.reference_date.isoformat() if report.reference_date else None
        )
        year_line_counts[str(year)] = len(report.lines)

    missing_statement_years = [
        year for year, report in reports_by_year.items() if not report.lines
    ]
    if missing_statement_years:
        raise RuntimeError(
            "CVM DFP returned no ITSA statement evidence for years: "
            + ", ".join(str(year) for year in missing_statement_years)
        )

    audit = audit_itsa_holding_schema_stability(
        reports_by_year,
        start_year=args.start_year,
        end_year=args.end_year,
        baseline_year=args.baseline_year,
    )

    review_candidates = [
        {
            "concept_id": result.concept_id,
            "statement": result.statement,
            "account_code": result.account_code,
            "tier": result.tier,
            "baseline_label": result.baseline_label,
            "status": result.status,
            "missing_years": list(result.missing_years),
            "distinct_labels": list(result.distinct_labels),
        }
        for result in audit.schema_stability.results
        if result.status != STATUS_STABLE_EXACT
    ]
    core_review_candidates = [
        item for item in review_candidates if item["tier"] == "core"
    ]

    payload = {
        "generated_at": collected_at.isoformat(),
        "source": "CVM_DFP_CIA_ABERTA",
        "company_id": ITSA_COMPANY_ID,
        "start_year": args.start_year,
        "end_year": args.end_year,
        "baseline_year": args.baseline_year,
        "statement_scope": "individual",
        "year_reference_dates": year_reference_dates,
        "year_line_counts": year_line_counts,
        "audit": audit.to_dict(),
        "review_candidates": review_candidates,
        "core_review_candidates": core_review_candidates,
        "notes": [
            (
                "Diagnostic only: this audit does not define a holding score, peer set, "
                "routing rule, rankability change or applicability-registry resolution."
            ),
            (
                "The seven account codes come from the prior official 2025 ITSA holding "
                "diagnostic; baseline labels are read from the exact 2025 DFP statement "
                "tree and are never guessed."
            ),
            (
                "Each annual archive is filtered to exact CD_CVM=7617 before "
                "statement-tree normalization."
            ),
            (
                "Exact statement + account_code is required. Missing codes remain UNKNOWN "
                "and label drift is surfaced for review; semantic remapping by name is "
                "prohibited."
            ),
            (
                "Investment parent and child accounts are reported separately. The "
                "investments/assets ratio uses only exact parent code 1.02.02, so nested "
                "participation rows are never double counted."
            ),
            (
                "Economic ratios are descriptive evidence only. No threshold in this "
                "artifact creates a score, recommendation or structural-model decision."
            ),
            (
                "Current CVM annual archives are latest-state snapshots and are not treated "
                "as complete revision-aware point-in-time evidence for historical backtests."
            ),
        ],
    }
    Path(args.output).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, default=str)
        + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
