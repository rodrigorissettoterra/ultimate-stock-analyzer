from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from ultimate_stock_analyzer.backtesting.b3_sector_pit_source_audit import (
    B3_CLASSIFICATION_CURRENT_SNAPSHOT_ONLY,
    HISTORICAL_SECTOR_ROUTING_SOURCE_UNPROVEN,
    audit_b3_sector_pit_source,
)
from ultimate_stock_analyzer.collectors.b3_classification import B3IndustryClassificationCollector

B3_CLASSIFICATION_SOURCE_PAGE = (
    "https://www.b3.com.br/pt_br/produtos-e-servicos/negociacao/"
    "renda-variavel/acoes/consultas/classificacao-setorial/"
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Audit whether the official current B3 industry-classification workbook "
            "can support historical point-in-time sector routing."
        )
    )
    parser.add_argument("--start-year", type=int, default=2024)
    parser.add_argument("--end-year", type=int, default=2025)
    parser.add_argument("--output", default="b3-sector-pit-source-audit.json")
    return parser


def main() -> None:
    args = _parser().parse_args()
    if args.start_year > args.end_year:
        raise SystemExit("start-year must not be after end-year")
    collected_at = datetime.now(UTC)
    collector = B3IndustryClassificationCollector()
    workbook_content = collector.download_workbook()
    rows = collector.parse_workbook(workbook_content)
    audit = audit_b3_sector_pit_source(
        workbook_content=workbook_content,
        classification_record_count=len(rows),
        collected_at=collected_at,
        source_page_url=B3_CLASSIFICATION_SOURCE_PAGE,
        requested_start_year=args.start_year,
        requested_end_year=args.end_year,
    )
    report = audit.to_dict()
    report["source_policy_reference"] = (
        "B3 states that the consultation base is updated weekly on the last business day; "
        "the public download exposes the current workbook, not dated historical snapshots."
    )
    report["warnings"] = [
        "COLLECTION_TIME_CAN_START_FORWARD_LINEAGE_ONLY",
        "CURRENT_CLASSIFICATION_MUST_NOT_BE_RETROJECTED",
        "UNLABELLED_WORKBOOK_DATE_LITERALS_HAVE_NO_AS_OF_SEMANTICS",
        "NO_SECTOR_ROUTING_OR_READINESS_CHANGE_IN_THIS_BLOCK",
    ]
    required = {
        B3_CLASSIFICATION_CURRENT_SNAPSHOT_ONLY,
        HISTORICAL_SECTOR_ROUTING_SOURCE_UNPROVEN,
    }
    if not required.issubset(audit.blockers):
        raise RuntimeError("fail-closed historical sector blockers must remain")
    Path(args.output).write_text(
        json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True),
        encoding="utf-8",
    )
    print(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
