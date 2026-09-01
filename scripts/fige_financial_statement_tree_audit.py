from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from ultimate_stock_analyzer.orchestration.cvm_ingestion import CVMIngestionService
from ultimate_stock_analyzer.scoring.statement_tree_audit import (
    audit_financial_statement_tree,
)

FIGE_COMPANY_ID = "cvm:6041"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate a bounded CVM DFP account-tree diagnostic for FIGE."
    )
    parser.add_argument("--year", type=int, default=2025)
    parser.add_argument("--max-depth", type=int, default=4)
    parser.add_argument(
        "--output",
        default="fige-financial-statement-tree-audit.json",
    )
    args = parser.parse_args()

    collected_at = datetime.now(UTC)
    lines = CVMIngestionService().load_statements(
        document_type="DFP",
        year=args.year,
        statements=("BPA", "BPP", "DRE"),
        scope_token="ind",
        collected_at=collected_at,
    )
    report = audit_financial_statement_tree(
        lines,
        company_id=FIGE_COMPANY_ID,
        max_depth=args.max_depth,
    )
    if report.reference_date is None or not report.lines:
        raise RuntimeError(
            "CVM DFP returned no FIGE statement tree: "
            f"company_id={FIGE_COMPANY_ID} year={args.year}"
        )

    payload = {
        "generated_at": collected_at.isoformat(),
        "source": "CVM_DFP_CIA_ABERTA",
        "document_type": "DFP",
        "fiscal_year": args.year,
        "statement_scope": "individual",
        "audit": report.to_dict(),
        "notes": [
            "Diagnostic only: this artifact inventories official FIGE account codes and labels and does not establish scoring mappings.",
            "Only canonical company_id=cvm:6041 is used; ticker/name/fuzzy issuer matching is not used.",
            "Latest reference-date rows use fiscal_order=ÚLTIMO and the highest filing version/document_id for duplicate exact codes.",
            "The account tree is bounded by max_depth to expose the financial template without persisting the full CVM archive.",
            "Missing accounts remain absent/UNKNOWN and are never represented as zero.",
            "Current CVM downloads are not treated as revision-aware point-in-time evidence for historical backtests.",
        ],
    }
    Path(args.output).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, default=str)
        + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
