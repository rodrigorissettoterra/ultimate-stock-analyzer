from __future__ import annotations

import argparse
import json
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

from ultimate_stock_analyzer.collectors.cvm_foreign import CVMForeignIssuerCollector

DEFAULT_EXPECTED_FOREIGN = ("cvm:80195", "cvm:80152")
DEFAULT_NEGATIVE_CONTROLS = ("cvm:9512",)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Audit canonical CVM identities against the official foreign-issuer registry."
    )
    parser.add_argument("--foreign-company-id", action="append", default=[])
    parser.add_argument("--negative-control-company-id", action="append", default=[])
    parser.add_argument("--output", default="cvm-foreign-issuer-audit.json")
    args = parser.parse_args()

    expected_foreign = tuple(args.foreign_company_id) or DEFAULT_EXPECTED_FOREIGN
    negative_controls = (
        tuple(args.negative_control_company_id) or DEFAULT_NEGATIVE_CONTROLS
    )
    collected_at = datetime.now(UTC)
    collector = CVMForeignIssuerCollector()
    records = collector.collect(collected_at=collected_at)
    by_company: defaultdict[str, list[object]] = defaultdict(list)
    for record in records:
        by_company[record.company_id].append(record)

    missing_expected = sorted(
        company_id for company_id in expected_foreign if company_id not in by_company
    )
    false_positive_controls = sorted(
        company_id for company_id in negative_controls if company_id in by_company
    )
    if missing_expected:
        raise RuntimeError(
            "Expected canonical foreign issuers absent from official CVM registry: "
            + ", ".join(missing_expected)
        )
    if false_positive_controls:
        raise RuntimeError(
            "Brazilian-company negative controls unexpectedly present in foreign registry: "
            + ", ".join(false_positive_controls)
        )

    selected = [
        record
        for record in records
        if record.company_id in set(expected_foreign)
    ]
    payload = {
        "generated_at": collected_at.isoformat(),
        "source": "CVM_FOREIGN_ISSUER_CAD",
        "source_url": collector.registry_url(),
        "snapshot_scope": "CURRENT_REGISTRY_STATE",
        "point_in_time_eligible": False,
        "decision_effect": "diagnostic_only",
        "expected_foreign_company_ids": sorted(expected_foreign),
        "negative_control_company_ids": sorted(negative_controls),
        "registry_rows": len(records),
        "selected_records": [
            {
                "company_id": record.company_id,
                "cvm_code": record.cvm_code,
                "legal_name": record.legal_name,
                "registration_status": record.registration_status,
                "registration_date": record.registration_date,
                "cancellation_date": record.cancellation_date,
            }
            for record in selected
        ],
        "notes": [
            "Identity is resolved directly by the official CVM code; no ticker or company-name matching is used.",
            "Presence in this registry establishes that the CVM participant is a foreign issuer, not a universe exclusion by itself in this diagnostic gate.",
            "The registry is a current-state source and must not be backfilled as historical point-in-time jurisdiction evidence.",
        ],
    }
    Path(args.output).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
