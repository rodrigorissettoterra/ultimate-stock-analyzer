from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from ultimate_stock_analyzer.orchestration.cvm_ingestion import CVMIngestionService
from ultimate_stock_analyzer.scoring.account_schema_audit import (
    audit_general_corporate_account_schema,
)

REVIEW_COMPANY_IDS = ("cvm:6041", "cvm:7617", "cvm:27634")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Audit exact CVM account-code labels used by the general_corporate "
            "fixed-account contract for unresolved model cases."
        )
    )
    parser.add_argument("--year", type=int, default=2025)
    parser.add_argument(
        "--output",
        default="general-corporate-account-schema-audit.json",
    )
    args = parser.parse_args()

    collected_at = datetime.now(UTC)
    service = CVMIngestionService()
    lines = service.load_statements(
        document_type="DFP",
        year=args.year,
        statements=("BPA", "BPP", "DRE"),
        scope_token="ind",
        collected_at=collected_at,
    )
    report = audit_general_corporate_account_schema(
        lines,
        company_ids=REVIEW_COMPANY_IDS,
    )

    companies_with_evidence = {
        observation.company_id
        for concept in report.concepts
        for observation in concept.observations
    }
    missing_companies = sorted(set(REVIEW_COMPANY_IDS) - companies_with_evidence)
    if missing_companies:
        raise RuntimeError(
            "Missing account-schema evidence for: " + ", ".join(missing_companies)
        )

    payload = {
        "generated_at": collected_at.isoformat(),
        "source": "CVM_DFP_CIA_ABERTA",
        "document_type": "DFP",
        "fiscal_year": args.year,
        "statement_scope": "individual",
        "review_company_ids": list(REVIEW_COMPANY_IDS),
        "report": report.to_dict(),
        "notes": [
            "Diagnostic only: different official account labels are surfaced and are not automatically treated as economically equivalent.",
            "The audit evaluates exact account codes already used by the general_corporate fixed-account contract for BPA/BPP/DRE only.",
            "Canonical issuer identity remains company_id=cvm:<CD_CVM>; ticker/name/fuzzy issuer matching is not used.",
            "Missing account evidence remains missing/UNKNOWN and is never converted to zero.",
            "The current CVM archive download is not treated as revision-aware point-in-time evidence for historical backtests.",
        ],
    }
    Path(args.output).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, default=str)
        + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
