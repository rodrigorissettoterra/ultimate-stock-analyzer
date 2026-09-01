from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from ultimate_stock_analyzer.collectors.cvm import CVMCollector
from ultimate_stock_analyzer.collectors.cvm_targeted_statements import (
    load_company_statements_from_archive,
)
from ultimate_stock_analyzer.fundamentals.itsa_holding_contract import (
    ITSA_COMPANY_ID,
    ITSA_CVM_CODE,
    ITSA_HOLDING_ACCOUNT_BINDINGS,
    evaluate_itsa_holding_contract,
)
from ultimate_stock_analyzer.scoring.statement_tree_audit import (
    audit_financial_statement_tree,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate the exact ITSA CVM holding accounting contract."
    )
    parser.add_argument("--year", type=int, default=2025)
    parser.add_argument(
        "--output",
        default="itsa-holding-accounting-contract-audit.json",
    )
    args = parser.parse_args()

    collected_at = datetime.now(UTC)
    collector = CVMCollector()
    archive = collector.download_zip("DFP", args.year)
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
    if not report.lines:
        raise RuntimeError(
            f"CVM DFP returned no ITSA statement evidence for year={args.year}"
        )

    evaluation = evaluate_itsa_holding_contract(report)
    expected_concepts = {
        binding.concept_id for binding in ITSA_HOLDING_ACCOUNT_BINDINGS
    }
    observed_concepts = set(evaluation.values)
    if observed_concepts != expected_concepts:
        missing = sorted(expected_concepts - observed_concepts)
        unexpected = sorted(observed_concepts - expected_concepts)
        raise RuntimeError(
            "ITSA holding accounting contract coverage is incomplete: "
            f"missing={missing} unexpected={unexpected}"
        )
    if evaluation.coverage.critical_coverage != 1.0:
        raise RuntimeError(
            "ITSA holding accounting contract critical coverage is below 100%"
        )

    payload = {
        "generated_at": collected_at.isoformat(),
        "source": "CVM_DFP_CIA_ABERTA",
        "document_type": "DFP",
        "fiscal_year": args.year,
        "statement_scope": "individual",
        "company_id": ITSA_COMPANY_ID,
        "evaluation": evaluation.to_dict(),
        "bindings": [asdict(binding) for binding in ITSA_HOLDING_ACCOUNT_BINDINGS],
        "notes": [
            (
                "The seven bindings were promoted only after exact statement/account-code "
                "and label stability was observed across ITSA DFP 2021-2025."
            ),
            (
                "Extraction is fail-closed by exact company identity, statement, account "
                "code and normalized label; fuzzy account-name remapping is prohibited."
            ),
            (
                "Nested investment accounts are separate concepts. Descriptive "
                "investments/assets uses only parent account 1.02.02 and never sums its "
                "children."
            ),
            (
                "This contract defines accounting semantics only. It does not define a "
                "holding score, peer set, routing rule, rankability or recommendation."
            ),
            (
                "Current annual CVM archives are latest-state snapshots and are not treated "
                "as complete revision-aware point-in-time history."
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
