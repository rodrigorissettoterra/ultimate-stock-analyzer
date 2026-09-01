from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from ultimate_stock_analyzer.collectors.cvm import CVMCollector
from ultimate_stock_analyzer.collectors.cvm_targeted_statements import (
    load_company_statements_from_archive,
)
from ultimate_stock_analyzer.fundamentals.fige_financial_contract import (
    FIGE_COMPANY_ID,
    evaluate_fige_financial_contract,
)
from ultimate_stock_analyzer.scoring.statement_tree_audit import (
    audit_financial_statement_tree,
)

FIGE_CVM_CODE = 6041


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate the FIGE CVM accounting contract across annual DFPs."
    )
    parser.add_argument("--start-year", type=int, default=2021)
    parser.add_argument("--end-year", type=int, default=2025)
    parser.add_argument(
        "--output",
        default="fige-financial-accounting-contract-audit.json",
    )
    args = parser.parse_args()

    if args.start_year > args.end_year:
        raise ValueError("start-year must not be greater than end-year")

    collected_at = datetime.now(UTC)
    collector = CVMCollector()
    annual_evaluations: list[dict[str, object]] = []
    incomplete_years: list[int] = []

    for year in range(args.start_year, args.end_year + 1):
        archive = collector.download_zip("DFP", year)
        lines = load_company_statements_from_archive(
            archive,
            cvm_code=FIGE_CVM_CODE,
            document_type="DFP",
            statements=("BPA", "BPP", "DRE"),
            scope_token="ind",
            collected_at=collected_at,
            collector=collector,
        )
        report = audit_financial_statement_tree(
            lines,
            company_id=FIGE_COMPANY_ID,
            max_depth=4,
        )
        if report.reference_date is None or not report.lines:
            incomplete_years.append(year)
            annual_evaluations.append(
                {
                    "fiscal_year": year,
                    "reference_date": None,
                    "status": "NO_FIGE_DFP_EVIDENCE",
                }
            )
            continue

        evaluation = evaluate_fige_financial_contract(report)
        coverage = evaluation.coverage
        complete = (
            coverage.critical_coverage == 1.0
            and coverage.total_coverage == 1.0
        )
        if not complete:
            incomplete_years.append(year)
        annual_evaluations.append(
            {
                "fiscal_year": year,
                "status": "COMPLETE" if complete else "INCOMPLETE",
                **evaluation.to_dict(),
            }
        )

    payload = {
        "generated_at": collected_at.isoformat(),
        "source": "CVM_DFP_CIA_ABERTA",
        "company_id": FIGE_COMPANY_ID,
        "start_year": args.start_year,
        "end_year": args.end_year,
        "effect": "contract_defined_not_routed",
        "point_in_time_eligible": False,
        "annual_evaluations": annual_evaluations,
        "incomplete_years": incomplete_years,
        "notes": [
            "The contract uses only exact FIGE statement/account-code bindings proven stable across 2021-2025.",
            "Each binding also validates the expected official CVM account label and fails closed on semantic drift.",
            "Annual raw CVM rows and filing metadata are filtered to exact CD_CVM=6041 before normalization.",
            "Missing bindings remain UNKNOWN; reported zero values remain known zero values.",
            "This block defines and validates an accounting contract only; it does not activate model routing or scoring.",
            "Latest-state CVM annual archives are not treated as complete revision-history PIT evidence for strict backtesting.",
        ],
    }
    Path(args.output).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, default=str)
        + "\n",
        encoding="utf-8",
    )

    if incomplete_years:
        raise RuntimeError(
            "FIGE financial accounting contract was incomplete for years: "
            + ", ".join(str(year) for year in incomplete_years)
        )


if __name__ == "__main__":
    main()
