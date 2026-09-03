from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

from ultimate_stock_analyzer.backtesting.cvm_bank_net_income_canonical_mapping_audit import (
    audit_cvm_bank_net_income_canonical_mapping,
)
from ultimate_stock_analyzer.collectors.cvm import CVMCollector
from ultimate_stock_analyzer.orchestration.cvm_ingestion import CVMIngestionService


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Validate observed CVM bank net-income account 3.09 across fiscal years "
            "and filing versions without promoting overall bank PIT readiness."
        )
    )
    parser.add_argument("--cvm-code", type=int, default=19348)
    parser.add_argument("--year", type=int, action="append", required=True)
    parser.add_argument(
        "--output",
        default="cvm-bank-net-income-canonical-mapping-audit.json",
    )
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
    target_lines = []

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
        target_lines.extend(
            service.load_company_statements_from_archive(
                archive,
                cvm_code=args.cvm_code,
                document_type="DFP",
                statements=("DRE",),
                scope_token="con",
                collected_at=generated_at,
            )
        )

    audit = audit_cvm_bank_net_income_canonical_mapping(
        target_lines,
        cvm_code=args.cvm_code,
        years=years,
    )
    report = {
        **audit.to_dict(),
        "generated_at": generated_at.isoformat(),
        "dfp_archives": archives,
        "versions_observed_by_year": {
            str(year): sorted(
                item.version for item in audit.versions if item.fiscal_year == year
            )
            for year in years
        },
        "strict_issuer_lineage": True,
        "warnings": [
            "OBSERVED_DFP_VERSIONS_DO_NOT_PROVE_COMPLETE_REVISION_HISTORY",
            "CANONICAL_MAPPING_SUPPORT_IS_LIMITED_TO_THE_AUDITED_ISSUER_AND_WINDOW",
            "CVM_ISSUER_ACCOUNTING_SCOPE_IS_NOT_YET_ALIGNED_TO_PRUDENTIAL_SCOPE",
            "NO_OVERALL_BANK_POINT_IN_TIME_READINESS_PROMOTION_IN_THIS_BLOCK",
        ],
    }
    Path(args.output).write_text(
        json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True),
        encoding="utf-8",
    )
    print(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
