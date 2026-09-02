from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ultimate_stock_analyzer.collectors.b3_corporate_actions import (
    B3CorporateActionsContractAuditor,
    READY_COMPLETE_FACTOR,
    SUPPORTED_SHARE_ACTION_LABELS,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Audit B3 stock-dividend and subscription semantics without adjusting prices.",
    )
    parser.add_argument(
        "--issuing-company",
        action="append",
        dest="issuing_companies",
        required=True,
        help="B3 issuing-company code such as ITSA or MGLU; repeat for multiple companies.",
    )
    parser.add_argument("--output", default="b3-corporate-actions-contract-audit.json")
    return parser


def main() -> None:
    args = _parser().parse_args()
    generated_at = datetime.now(UTC)
    auditor = B3CorporateActionsContractAuditor.default()
    company_audits = [auditor.audit(code) for code in args.issuing_companies]

    observed_labels = sorted(
        {
            label
            for company_audit in company_audits
            for label in company_audit.observed_stock_labels
        }
    )
    blockers = sorted(
        {
            blocker
            for company_audit in company_audits
            for blocker in company_audit.blockers
        }
    )
    stock_action_count = sum(len(audit.stock_actions) for audit in company_audits)
    supported_count = sum(
        sum(record.supported_label for record in audit.stock_actions)
        for audit in company_audits
    )
    ready_count = sum(audit.conversion_ready_stock_actions for audit in company_audits)
    ambiguous_count = sum(audit.ambiguous_stock_actions for audit in company_audits)
    subscription_count = sum(len(audit.subscriptions) for audit in company_audits)

    report: dict[str, Any] = {
        "schema_version": "0.1",
        "effect": "diagnostic_only_no_price_adjustment_or_backtest_promotion",
        "generated_at": generated_at.isoformat().replace("+00:00", "Z"),
        "source": "B3_PUBLIC_LISTED_COMPANIES",
        "issuing_companies": [audit.issuing_company for audit in company_audits],
        "supported_share_action_labels": sorted(SUPPORTED_SHARE_ACTION_LABELS),
        "observed_stock_action_labels": observed_labels,
        "stock_action_count": stock_action_count,
        "supported_stock_action_count": supported_count,
        "conversion_ready_stock_action_count": ready_count,
        "ambiguous_stock_action_count": ambiguous_count,
        "subscription_count": subscription_count,
        "blockers": blockers,
        "raw_factor_used_as_share_ratio_without_complete_factor": False,
        "share_action_conversion_applied": False,
        "price_adjustment_applied": False,
        "strict_backtest_price_readiness_changed": False,
        "companies": [audit.to_dict() for audit in company_audits],
        "warnings": [
            "RAW_FACTOR_IS_NOT_USED_AS_SHARE_RATIO_WITHOUT_EXPLICIT_RATIO_EVIDENCE",
            "SUBSCRIPTION_RIGHTS_REMAIN_UNSUPPORTED_BY_M15_RETURN_PREPARATION",
            "COTAHIST_REMAINS_UNADJUSTED_IN_THIS_AUDIT_BLOCK",
        ],
    }
    report["contract_conversion_ready"] = (
        stock_action_count > 0
        and supported_count == stock_action_count
        and ready_count == stock_action_count
        and ambiguous_count == 0
        and subscription_count == 0
        and all(
            record.conversion_status == READY_COMPLETE_FACTOR
            for audit in company_audits
            for record in audit.stock_actions
        )
    )

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
