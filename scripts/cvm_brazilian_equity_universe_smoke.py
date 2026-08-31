from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from ultimate_stock_analyzer.collectors.cvm_foreign import CVMForeignIssuerCollector
from ultimate_stock_analyzer.orchestration.cvm_ingestion import CVMIngestionService
from ultimate_stock_analyzer.universe.eligibility import classify_brazilian_equity_issuers

CONTROL_COMPANY_IDS = ("cvm:9512", "cvm:80152", "cvm:80195")
EXPECTED_STATUSES = {
    "cvm:9512": "ELIGIBLE_BRAZILIAN_PUBLIC_COMPANY",
    "cvm:80152": "EXCLUDED_FOREIGN_ISSUER",
    "cvm:80195": "EXCLUDED_FOREIGN_ISSUER",
}


def main() -> None:
    collected_at = datetime.now(UTC)
    domestic_service = CVMIngestionService()
    domestic = domestic_service.load_issuer_master(
        collected_at=collected_at,
        active_only=False,
    )
    foreign = CVMForeignIssuerCollector().collect(collected_at=collected_at)
    report = classify_brazilian_equity_issuers(
        CONTROL_COMPANY_IDS,
        brazilian_public_company_ids=(record.company_id for record in domestic),
        foreign_issuer_company_ids=(record.company_id for record in foreign),
    )
    observed = {decision.company_id: decision.status for decision in report.decisions}
    if observed != EXPECTED_STATUSES:
        raise RuntimeError(
            "Brazilian-equity universe jurisdiction controls changed: "
            f"expected={EXPECTED_STATUSES}, observed={observed}"
        )

    payload = {
        "generated_at": collected_at.isoformat(),
        "scope": "BRAZILIAN_COMPANY_EQUITIES",
        "identity_key": "company_id=cvm:<CD_CVM>",
        "source_contracts": ["CVM_CAD", "CVM_FOREIGN_ISSUER_CAD"],
        "point_in_time_eligible": False,
        "pipeline_effect": "contract_only_not_integrated_into_ranking",
        "report": report.to_dict(),
        "notes": [
            "Jurisdiction is resolved by canonical CVM identity across separate official CVM registries.",
            "Foreign-issuer exclusion is a universe-scope decision, not a structural-score penalty.",
            "No ticker suffix or company-name matching participates in eligibility.",
            "This current-state smoke cannot be reused as historical point-in-time eligibility evidence."
        ],
    }
    Path("cvm-brazilian-equity-universe.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
