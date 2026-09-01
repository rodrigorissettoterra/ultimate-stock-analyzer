from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from ultimate_stock_analyzer.orchestration.cvm_ingestion import CVMIngestionService
from ultimate_stock_analyzer.scoring.holding_model_audit import (
    audit_holding_model_data_contract,
)

REVIEW_COMPANY_IDS = ("cvm:6041", "cvm:7617", "cvm:27634")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Audit CVM DFP account evidence for unresolved holding-model cases."
    )
    parser.add_argument("--year", type=int, default=2025)
    parser.add_argument(
        "--output",
        default="holding-model-data-contract-audit.json",
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
    report = audit_holding_model_data_contract(
        lines,
        company_ids=REVIEW_COMPANY_IDS,
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
            "Diagnostic only: account-name matches expose candidate mappings and do not define scoring inputs.",
            "Issuer identity remains canonical company_id=cvm:<CD_CVM>; no ticker/name/fuzzy issuer matching is used.",
            "Candidate totals are withheld when multiple matching account rows could create parent/child double counting.",
            "This current download is not treated as revision-aware point-in-time evidence for historical backtests.",
        ],
    }

    audits = report.company_audits
    if any(audit.reference_date is None for audit in audits):
        missing = [audit.company_id for audit in audits if audit.reference_date is None]
        raise RuntimeError("Missing DFP statement evidence for: " + ", ".join(missing))

    Path(args.output).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
