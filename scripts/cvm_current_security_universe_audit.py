from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from ultimate_stock_analyzer.collectors.cvm import CVMCollector
from ultimate_stock_analyzer.orchestration.cvm_ingestion import CVMIngestionService
from ultimate_stock_analyzer.universe.security_audit import (
    audit_current_security_universe,
)

DEFAULT_COMPANY_IDS = (
    "cvm:6041",   # FIGE
    "cvm:18759",  # BSCS
    "cvm:27634",  # B100
    "cvm:7617",   # ITSA
    "cvm:9512",   # PETR control
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Audit current CVM FCA security types without making eligibility decisions."
    )
    parser.add_argument("--year", type=int, default=datetime.now(UTC).year)
    parser.add_argument("--company-id", action="append", default=[])
    parser.add_argument("--require-company-id", action="append", default=[])
    parser.add_argument("--output", default="cvm-current-security-universe-audit.json")
    args = parser.parse_args()

    collected_at = datetime.now(UTC)
    collector = CVMCollector()
    service = CVMIngestionService(collector=collector)
    service.load_issuer_master(collected_at=collected_at, active_only=False)
    securities = service.load_security_master(
        year=args.year,
        collected_at=collected_at,
    )
    selected = tuple(args.company_id) or DEFAULT_COMPANY_IDS
    report = audit_current_security_universe(
        securities,
        as_of=collected_at.date(),
        selected_company_ids=selected,
    )

    found_company_ids = {row.company_id for row in report.selected_rows}
    required = {str(value).strip().lower() for value in args.require_company_id}
    missing_required = sorted(required - found_company_ids)
    if missing_required:
        raise RuntimeError(
            "required FCA security controls were not found: " + ", ".join(missing_required)
        )

    payload = {
        "generated_at": collected_at.isoformat(),
        "year": args.year,
        "source": "CVM_FCA",
        "source_url": collector.dataset_url("FCA", args.year),
        "decision_effect": "diagnostic_only",
        "point_in_time_eligible": False,
        "report": report.to_dict(),
        "unmapped_security_tickers_sample": list(service.last_unmapped_security_tickers[:20]),
        "notes": [
            "This artifact audits observed FCA security fields and does not define equity eligibility.",
            "Identity is canonical company_id = cvm:<CD_CVM>; ticker is only a security label.",
            "Counts use the latest FCA row per canonical company_id+ticker and current trading-date bounds.",
            "Current FCA evidence must not be backfilled as historical point-in-time security eligibility.",
        ],
    }
    Path(args.output).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
