from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, date, datetime
from pathlib import Path

import httpx

from ultimate_stock_analyzer.backtesting.cvm_ipe_pillar3_filing_ledger import (
    BANK_EVIDENCE_NOT_POINT_IN_TIME,
    PILLAR3_IPE_EXACT_DELIVERY_TIMESTAMP_UNAVAILABLE,
    PILLAR3_IPE_HISTORICAL_SNAPSHOT_UNAVAILABLE,
    PILLAR3_IPE_HISTORICAL_STATUS_UNAVAILABLE,
    PILLAR3_IPE_OPEN_DATA_EXPORT_COMPLETENESS_UNPROVEN,
    PILLAR3_IPE_REVISION_HISTORY_COMPLETENESS_UNPROVEN,
    PILLAR3_PDF_CONTENT_UNVALIDATED,
    PILLAR3_PRUDENTIAL_METRIC_COVERAGE_UNPROVEN,
    CVMIPEArchiveSnapshot,
    audit_cvm_ipe_pillar3_filing_ledger,
)
from ultimate_stock_analyzer.collectors.cvm_ipe import (
    CVMIPECollector,
    CVMIPEDocument,
    inspect_cvm_ipe_zip_columns,
    parse_cvm_ipe_zip,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Audit the official CVM IPE filing ledger for annual Pillar 3 reports "
            "and preserve explicit revision-completeness blockers."
        )
    )
    parser.add_argument("--cvm-code", type=int, default=19348)
    parser.add_argument(
        "--reference-date",
        action="append",
        required=True,
        help="Annual prudential reference date (YYYY-MM-DD); repeat as needed.",
    )
    parser.add_argument(
        "--output",
        default="cvm-ipe-pillar3-filing-ledger-audit.json",
    )
    return parser


def main() -> None:
    args = _parser().parse_args()
    if args.cvm_code <= 0:
        raise SystemExit("cvm-code must be positive")
    reference_dates = _reference_dates(args.reference_date)
    generated_at = datetime.now(UTC)
    source_years = tuple(
        range(
            min(item.year for item in reference_dates),
            generated_at.year + 1,
        )
    )

    collector = CVMIPECollector()
    documents: list[CVMIPEDocument] = []
    snapshots: list[CVMIPEArchiveSnapshot] = []
    with httpx.Client(
        timeout=collector.timeout_seconds,
        follow_redirects=True,
        headers={"User-Agent": collector.user_agent},
    ) as client:
        for year in source_years:
            url = collector.dataset_url(year)
            response = client.get(url)
            response.raise_for_status()
            content = response.content
            columns = inspect_cvm_ipe_zip_columns(content)
            snapshots.append(
                CVMIPEArchiveSnapshot(
                    source_year=year,
                    source_url=url,
                    sha256=hashlib.sha256(content).hexdigest(),
                    size_bytes=len(content),
                    columns=columns,
                )
            )
            documents.extend(
                parse_cvm_ipe_zip(
                    content,
                    year=year,
                    cvm_codes={args.cvm_code},
                )
            )

    audit = audit_cvm_ipe_pillar3_filing_ledger(
        cvm_code=args.cvm_code,
        documents=documents,
        source_archives=snapshots,
        requested_reference_dates=reference_dates,
        generated_at=generated_at,
    )
    report = audit.to_dict()
    report["source_years_downloaded"] = list(source_years)
    report["warnings"] = [
        "IPE_PUBLIC_VERSION_RETENTION_DOES_NOT_PROVE_OPEN_DATA_EXPORT_COMPLETENESS",
        "CURRENT_ZIPS_ARE_NOT_IMMUTABLE_HISTORICAL_AS_OF_SNAPSHOTS",
        "PUBLIC_ENET_VISIBILITY_CAN_BE_INHIBITED_AFTER_PUBLICATION",
        "HISTORICAL_IPE_STATUS_REMAINS_UNPROVEN",
        "DOCUMENT_AVAILABILITY_USES_DELIVERY_DATE_PLUS_ONE_DAY",
        "PILLAR3_PDF_CONTENT_IS_NOT_PARSED_IN_THIS_BLOCK",
        "NO_BANK_READINESS_CHANGE_IN_THIS_BLOCK",
    ]

    required = {
        BANK_EVIDENCE_NOT_POINT_IN_TIME,
        PILLAR3_IPE_EXACT_DELIVERY_TIMESTAMP_UNAVAILABLE,
        PILLAR3_IPE_HISTORICAL_SNAPSHOT_UNAVAILABLE,
        PILLAR3_IPE_HISTORICAL_STATUS_UNAVAILABLE,
        PILLAR3_IPE_OPEN_DATA_EXPORT_COMPLETENESS_UNPROVEN,
        PILLAR3_IPE_REVISION_HISTORY_COMPLETENESS_UNPROVEN,
        PILLAR3_PDF_CONTENT_UNVALIDATED,
        PILLAR3_PRUDENTIAL_METRIC_COVERAGE_UNPROVEN,
    }
    if not required.issubset(report["blockers"]):
        raise RuntimeError("fail-closed Pillar 3 blockers must always remain")
    if report["bank_evidence_point_in_time_ready"] or report["readiness_promotion_allowed"]:
        raise RuntimeError("diagnostic Pillar 3 ledger must not promote bank readiness")
    for snapshot in report["source_archives"]:
        if not snapshot["columns"]:
            raise RuntimeError("raw CVM IPE archive schema must be captured")

    Path(args.output).write_text(
        json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True),
        encoding="utf-8",
    )
    print(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True))


def _reference_dates(values: list[str]) -> tuple[date, ...]:
    parsed = []
    for value in values:
        try:
            reference_date = date.fromisoformat(value)
        except ValueError as error:
            raise SystemExit(f"invalid reference date {value!r}") from error
        if reference_date.month != 12 or reference_date.day != 31:
            raise SystemExit("reference dates must be annual 31 December dates")
        parsed.append(reference_date)
    if len(set(parsed)) != len(parsed):
        raise SystemExit("reference dates must not contain duplicates")
    return tuple(sorted(parsed))


if __name__ == "__main__":
    main()
