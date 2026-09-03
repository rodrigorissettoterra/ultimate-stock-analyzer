from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

from ultimate_stock_analyzer.backtesting.cvm_bank_net_income_account_audit import (
    CVM_BANK_NET_INCOME_ACCOUNT_UNPROVEN,
    audit_cvm_bank_net_income_accounts,
)
from ultimate_stock_analyzer.collectors.cvm import CVMCollector
from ultimate_stock_analyzer.normalization.cvm import point_in_time_lines
from ultimate_stock_analyzer.orchestration.cvm_ingestion import CVMIngestionService


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Audit CVM DFP bank net-income account mapping without promoting it."
    )
    parser.add_argument("--cvm-code", type=int, default=19348)
    parser.add_argument("--year", type=int, action="append", required=True)
    parser.add_argument("--output", default="cvm-bank-net-income-account-audit.json")
    return parser


def main() -> None:
    args = _parser().parse_args()
    years = tuple(sorted(set(args.year)))
    if len(years) != len(args.year):
        raise SystemExit("years must not contain duplicates")

    generated_at = datetime.now(UTC)
    collector = CVMCollector(timeout_seconds=180.0)
    service = CVMIngestionService(collector)
    archives: list[dict[str, object]] = []
    periods: list[dict[str, object]] = []

    for year in years:
        archive = collector.download_zip("DFP", year)
        archives.append(
            {
                "year": year,
                "source_url": collector.dataset_url("DFP", year),
                "sha256": hashlib.sha256(archive).hexdigest(),
                "size_bytes": len(archive),
            }
        )
        lines = service.load_statements_from_archive(
            archive,
            document_type="DFP",
            statements=("DRE",),
            scope_token="con",
            collected_at=generated_at,
        )
        latest = point_in_time_lines(lines, as_of=generated_at)
        audit = audit_cvm_bank_net_income_accounts(
            latest,
            cvm_code=args.cvm_code,
            fiscal_year=year,
        )
        if audit.dre_line_count <= 0:
            raise RuntimeError(f"no consolidated CVM DRE lines found for {year}")
        if CVM_BANK_NET_INCOME_ACCOUNT_UNPROVEN not in audit.blockers:
            raise RuntimeError("bank net-income mapping blocker disappeared")
        if audit.mapping_proven or audit.readiness_promotion_allowed:
            raise RuntimeError("diagnostic account audit must remain fail-closed")
        periods.append(audit.to_dict())

    report = {
        "schema_version": "0.1",
        "effect": "diagnostic_only_cvm_bank_net_income_account_mapping",
        "company_id": f"cvm:{args.cvm_code}",
        "generated_at": generated_at.isoformat(),
        "audited_years": list(years),
        "dfp_archives": archives,
        "periods": periods,
        "mapping_proven": False,
        "readiness_promotion_allowed": False,
        "warnings": [
            "FIXED_ACCOUNT_3_11_IS_NOT_ASSUMED_FOR_BANKS",
            "DESCRIPTION_MATCHES_ARE_DIAGNOSTIC_CANDIDATES_NOT_CANONICAL_MAPPINGS",
            "CVM_DFP_ISSUER_SCOPE_IS_NOT_YET_ALIGNED_TO_PRUDENTIAL_CONGLOMERATE_SCOPE",
            "NO_BANK_READINESS_CHANGE_IN_THIS_BLOCK",
        ],
    }
    Path(args.output).write_text(
        json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True),
        encoding="utf-8",
    )
    print(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
