from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from ultimate_stock_analyzer.orchestration.cvm_ingestion import CVMIngestionService
from ultimate_stock_analyzer.scoring.security_universe_audit import audit_security_types


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Audit exact FCA/CVM security-type fields without making eligibility decisions."
    )
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--ticker", action="append", default=[])
    parser.add_argument("--output", default="cvm-security-type-audit.json")
    args = parser.parse_args()

    requested = tuple(args.ticker) or ("PETR4", "G2DI33", "PPLA11")
    collected_at = datetime.now(UTC)
    service = CVMIngestionService()
    service.load_issuer_master(collected_at=collected_at, active_only=False)
    securities = service.load_security_master(
        year=args.year,
        collected_at=collected_at,
    )
    report = audit_security_types(securities, tickers=requested)

    if "PETR4" in report.requested_tickers and "PETR4" not in report.found_tickers:
        raise RuntimeError("PETR4 control ticker is missing from normalized FCA security master")

    payload = {
        "generated_at": collected_at.isoformat(),
        "year": args.year,
        "source": "CVM_FCA",
        "decision_effect": "diagnostic_only",
        "unmapped_security_tickers_sample": list(service.last_unmapped_security_tickers[:20]),
        "report": report.to_dict(),
        "notes": [
            "This artifact preserves exact normalized FCA/CVM security-type fields for bounded audit cases.",
            "No security is included in or excluded from the investment universe by this audit.",
            "Ticker is used only to select security records; issuer identity remains company_id = cvm:<CD_CVM>.",
            "A later gate may define deterministic universe eligibility only after observed official field values are reviewed.",
        ],
    }
    Path(args.output).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
