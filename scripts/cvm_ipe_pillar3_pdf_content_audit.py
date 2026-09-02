from __future__ import annotations

import argparse
import hashlib
import io
import json
from datetime import UTC, date, datetime
from pathlib import Path

import httpx
from pypdf import PdfReader

from ultimate_stock_analyzer.backtesting.cvm_ipe_pillar3_filing_ledger import (
    CVMIPEArchiveSnapshot,
    audit_cvm_ipe_pillar3_filing_ledger,
)
from ultimate_stock_analyzer.backtesting.cvm_ipe_pillar3_pdf_content import (
    BANK_EVIDENCE_NOT_POINT_IN_TIME,
    PILLAR3_IPE_REVISION_HISTORY_COMPLETENESS_UNPROVEN,
    assess_pillar3_pdf_text,
    audit_pillar3_pdf_content,
)
from ultimate_stock_analyzer.collectors.cvm_ipe import CVMIPECollector, parse_cvm_ipe_zip


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Download versioned official CVM RAD Pillar 3 PDFs discovered through the IPE "
            "ledger and validate reference-period, KM1 and prudential-metric text coverage."
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
        default="cvm-ipe-pillar3-pdf-content-audit.json",
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
            min(item.year for item in reference_dates) + 1,
            generated_at.year + 1,
        )
    )
    if not source_years:
        raise SystemExit("requested reference dates do not have an observable delivery year yet")

    collector = CVMIPECollector()
    documents = []
    snapshots = []
    headers = {
        "User-Agent": collector.user_agent,
        "Accept": "application/pdf,application/octet-stream;q=0.9,*/*;q=0.8",
    }
    with httpx.Client(
        timeout=collector.timeout_seconds,
        follow_redirects=True,
        headers=headers,
    ) as client:
        for year in source_years:
            url = collector.dataset_url(year)
            response = client.get(url)
            response.raise_for_status()
            content = response.content
            snapshots.append(
                CVMIPEArchiveSnapshot(
                    source_year=year,
                    source_url=url,
                    sha256=hashlib.sha256(content).hexdigest(),
                    size_bytes=len(content),
                )
            )
            documents.extend(
                parse_cvm_ipe_zip(
                    content,
                    year=year,
                    cvm_codes={args.cvm_code},
                )
            )

        ledger = audit_cvm_ipe_pillar3_filing_ledger(
            cvm_code=args.cvm_code,
            documents=documents,
            source_archives=snapshots,
            requested_reference_dates=reference_dates,
            generated_at=generated_at,
        )
        filing_rows = tuple(
            filing
            for timeline in ledger.timelines
            for filing in timeline.filings
        )
        if not filing_rows:
            raise RuntimeError("official IPE ledger exposed no requested Pillar 3 filings")

        observations = []
        for filing in filing_rows:
            document = filing.document
            if (
                document.download_url is None
                or document.delivery_protocol is None
                or document.version is None
            ):
                raise RuntimeError("Pillar 3 filing lacks URL, protocol or version")
            response = client.get(document.download_url)
            response.raise_for_status()
            pdf_content = response.content
            if not pdf_content.startswith(b"%PDF-"):
                content_type = response.headers.get("content-type", "")
                raise RuntimeError(
                    f"RAD response is not a PDF for protocol {document.delivery_protocol}; "
                    f"content-type={content_type!r}"
                )
            reader = PdfReader(io.BytesIO(pdf_content), strict=False)
            extracted_text = "\n".join(page.extract_text() or "" for page in reader.pages)
            observations.append(
                assess_pillar3_pdf_text(
                    prudential_reference_date=filing.prudential_reference_date,
                    available_from=document.available_from,
                    delivery_protocol=document.delivery_protocol,
                    version=document.version,
                    source_url=document.download_url,
                    pdf_sha256=hashlib.sha256(pdf_content).hexdigest(),
                    size_bytes=len(pdf_content),
                    page_count=len(reader.pages),
                    extracted_text=extracted_text,
                    extracted_text_sha256=hashlib.sha256(
                        extracted_text.encode("utf-8")
                    ).hexdigest(),
                )
            )

    audit = audit_pillar3_pdf_content(
        requested_reference_dates=reference_dates,
        observations=observations,
    )
    report = audit.to_dict()
    report["company_id"] = ledger.company_id
    report["cvm_code"] = ledger.cvm_code
    report["generated_at"] = generated_at.isoformat()
    report["source_years_downloaded"] = list(source_years)
    report["source_archives"] = [
        {
            "source_year": item.source_year,
            "source_url": item.source_url,
            "sha256": item.sha256,
            "size_bytes": item.size_bytes,
        }
        for item in snapshots
    ]
    report["observed_filing_count"] = len(filing_rows)
    report["periods_with_multiple_observed_filings"] = (
        ledger.periods_with_multiple_observed_filings
    )
    report["filing_ledger"] = ledger.to_dict()
    report["warnings"] = [
        "PDF_LABEL_COVERAGE_DOES_NOT_YET_EXTRACT_NUMERIC_KM1_VALUES",
        "OBSERVED_IPE_VERSIONS_DO_NOT_YET_PROVE_GLOBAL_REVISION_COMPLETENESS",
        "NO_BANK_READINESS_CHANGE_IN_THIS_BLOCK",
    ]

    required = {
        BANK_EVIDENCE_NOT_POINT_IN_TIME,
        PILLAR3_IPE_REVISION_HISTORY_COMPLETENESS_UNPROVEN,
    }
    if not required.issubset(report["blockers"]):
        raise RuntimeError("fail-closed bank/revision blockers must remain")
    if report["bank_evidence_point_in_time_ready"] or report["readiness_promotion_allowed"]:
        raise RuntimeError("PDF validation must not promote bank readiness")

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
