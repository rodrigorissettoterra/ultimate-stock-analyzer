from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from ultimate_stock_analyzer.collectors.cvm import CVMCollector
from ultimate_stock_analyzer.collectors.cvm_targeted_statements import (
    load_company_statements_from_archive,
)
from ultimate_stock_analyzer.scoring.b100_accounting_lifecycle import (
    B100_CVM_CODE,
    audit_b100_accounting_lifecycle,
)

BASE_STATEMENTS = ("BPA", "BPP", "DRE")
CASH_FLOW_STATEMENTS = ("DFC_MI", "DFC_MD")
DEFAULT_SNAPSHOTS = (
    ("DFP", 2024),
    ("DFP", 2025),
    ("ITR", 2026),
)
SCOPE_TOKENS = ("ind", "con")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Audit B100 accounting lifecycle across DFP 2024/2025 and current ITR 2026, "
            "comparing individual and consolidated scopes without changing routing."
        )
    )
    parser.add_argument(
        "--output",
        default="b100-accounting-lifecycle-audit.json",
    )
    args = parser.parse_args()

    collected_at = datetime.now(UTC)
    collector = CVMCollector()
    snapshots = {}
    statement_sets: dict[str, list[str]] = {}
    archive_file_counts: dict[str, int] = {}

    for document_type, fiscal_year in DEFAULT_SNAPSHOTS:
        archive = collector.download_zip(document_type, fiscal_year)
        filenames = collector.list_csv_files(archive)
        archive_key = f"{document_type}_{fiscal_year}"
        archive_file_counts[archive_key] = len(filenames)

        for scope_token in SCOPE_TOKENS:
            snapshot_id = f"{document_type}_{fiscal_year}_{scope_token}"
            statements = _available_statements(
                filenames,
                document_type=document_type,
                fiscal_year=fiscal_year,
                scope_token=scope_token,
            )
            statement_sets[snapshot_id] = list(statements)
            snapshots[(document_type, fiscal_year, scope_token)] = (
                load_company_statements_from_archive(
                    archive,
                    cvm_code=B100_CVM_CODE,
                    document_type=document_type,
                    statements=statements,
                    scope_token=scope_token,
                    collected_at=collected_at,
                    collector=collector,
                )
            )

    report = audit_b100_accounting_lifecycle(snapshots)
    if report.evidence_snapshot_count == 0:
        raise RuntimeError("CVM returned no B100 accounting evidence in requested snapshots")

    payload = {
        "generated_at": collected_at.isoformat(),
        "source": "CVM_DFP_CIA_ABERTA+CVM_ITR_CIA_ABERTA",
        "requested_snapshots": [
            {"document_type": document, "fiscal_year": year}
            for document, year in DEFAULT_SNAPSHOTS
        ],
        "scope_tokens": list(SCOPE_TOKENS),
        "archive_file_counts": archive_file_counts,
        "statement_sets_by_snapshot": statement_sets,
        "audit": report.to_dict(),
        "notes": [
            "Diagnostic only: no B100 score, routing, rankability, valuation or applicability-registry change is made by this artifact.",
            "The audit compares both individual and consolidated issuer-bounded CVM scopes because B100 has a short public-company lifecycle and recent corporate reorganization evidence.",
            "BPA, BPP and DRE files are mandatory for every archive/scope. DFC_MI and DFC_MD are included only when that exact archive file exists and their availability is recorded explicitly.",
            "General-corporate coverage and ITSA holding-schema compatibility are measured independently; neither comparator automatically defines B100's economic model.",
            "Missing B100 rows or concepts remain missing/UNKNOWN and are never converted to zero.",
            "The latest reference date inside each archive/scope is used, so ITR 2026 represents the latest interim filing available in the current archive rather than a fabricated full-year value.",
            "Current CVM annual/interim archives are latest-state snapshots and are not treated as complete revision-aware point-in-time evidence for historical backtests.",
        ],
    }
    Path(args.output).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, default=str)
        + "\n",
        encoding="utf-8",
    )


def _available_statements(
    filenames: list[str],
    *,
    document_type: str,
    fiscal_year: int,
    scope_token: str,
) -> tuple[str, ...]:
    available: list[str] = []
    for statement in (*BASE_STATEMENTS, *CASH_FLOW_STATEMENTS):
        needle = f"_{statement.lower()}_{scope_token.lower()}_"
        matches = [name for name in filenames if needle in name.lower()]
        if len(matches) > 1:
            raise RuntimeError(
                "ambiguous CVM statement file in B100 lifecycle audit: "
                f"document={document_type} year={fiscal_year} scope={scope_token} "
                f"statement={statement} matches={len(matches)}"
            )
        if matches:
            available.append(statement)
        elif statement in BASE_STATEMENTS:
            raise RuntimeError(
                "required CVM statement file missing in B100 lifecycle audit: "
                f"document={document_type} year={fiscal_year} scope={scope_token} "
                f"statement={statement}"
            )
    return tuple(available)


if __name__ == "__main__":
    main()
