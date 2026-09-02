from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from ultimate_stock_analyzer.backtesting.cvm_ipe_corporate_action_ledger import (
    CVM_IPE_DOCUMENTS_UNSTRUCTURED,
    STRUCTURED_EVENT_HISTORY_COMPLETENESS_UNPROVEN,
    audit_cvm_ipe_corporate_action_ledger,
)
from ultimate_stock_analyzer.collectors.b3_dividends import B3DividendCollector
from ultimate_stock_analyzer.collectors.cvm_ipe import CVMIPECollector


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Cross-reference observed B3 corporate events with the historical CVM IPE "
            "document ledger without inferring structured event terms."
        )
    )
    parser.add_argument(
        "--sample",
        action="append",
        required=True,
        help="Sample in B3_COMPANY:TICKER:CVM_CODE form; repeat as needed.",
    )
    parser.add_argument("--start-year", type=int, default=2020)
    parser.add_argument("--end-year", type=int, default=2025)
    parser.add_argument(
        "--output",
        default="cvm-ipe-corporate-action-ledger-audit.json",
    )
    return parser


def main() -> None:
    args = _parser().parse_args()
    if args.start_year > args.end_year:
        raise SystemExit("start-year must not be after end-year")
    samples = _parse_samples(args.sample)
    generated_at = datetime.now(UTC)
    start_date = date(args.start_year, 1, 1)
    end_date = date(args.end_year, 12, 31)

    b3 = B3DividendCollector()
    payloads = {
        issuing_company: b3.fetch_payload(issuing_company)
        for issuing_company, _, _ in samples
    }
    cvm_codes = {cvm_code for _, _, cvm_code in samples}
    source_years = tuple(range(args.start_year, args.end_year + 1))
    cvm_ipe = CVMIPECollector()
    documents = tuple(
        document
        for year in source_years
        for document in cvm_ipe.fetch_year(year, cvm_codes=cvm_codes)
    )

    audits = tuple(
        audit_cvm_ipe_corporate_action_ledger(
            issuing_company=issuing_company,
            ticker=ticker,
            cvm_code=cvm_code,
            b3_payload=payloads[issuing_company],
            documents=documents,
            source_years=source_years,
            start_date=start_date,
            end_date=end_date,
            generated_at=generated_at,
        )
        for issuing_company, ticker, cvm_code in samples
    )
    blockers = sorted({blocker for audit in audits for blocker in audit.blockers})
    status_counts = Counter(
        corroboration.status
        for audit in audits
        for corroboration in audit.corroborations
    )
    report = {
        "schema_version": "0.1",
        "effect": "diagnostic_only_cvm_ipe_ledger_no_readiness_change",
        "generated_at": generated_at.isoformat(),
        "start_year": args.start_year,
        "end_year": args.end_year,
        "source_years_downloaded": list(source_years),
        "sample_count": len(audits),
        "samples": [
            {
                "issuing_company": issuing_company,
                "ticker": ticker,
                "company_id": f"cvm:{cvm_code}",
            }
            for issuing_company, ticker, cvm_code in samples
        ],
        "issuer_document_count": sum(audit.issuer_document_count for audit in audits),
        "observed_event_count": sum(audit.observed_event_count for audit in audits),
        "observed_stock_event_count": sum(
            audit.observed_stock_event_count for audit in audits
        ),
        "observed_cash_event_count": sum(
            audit.observed_cash_event_count for audit in audits
        ),
        "observed_subscription_count": sum(
            audit.observed_subscription_count for audit in audits
        ),
        "events_with_same_reference_date_documents": sum(
            audit.events_with_same_reference_date_documents for audit in audits
        ),
        "events_with_documents_available_by_com": sum(
            audit.events_with_documents_available_by_com for audit in audits
        ),
        "exact_reference_date_candidate_count": sum(
            audit.exact_reference_date_candidate_count for audit in audits
        ),
        "corroboration_status_counts": dict(sorted(status_counts.items())),
        "historical_document_archive_available": all(
            audit.historical_document_archive_available for audit in audits
        ),
        "observed_event_document_corroboration_complete": all(
            audit.observed_event_document_corroboration_complete for audit in audits
        ),
        "observed_event_pit_document_corroboration_complete": all(
            audit.observed_event_pit_document_corroboration_complete for audit in audits
        ),
        "structured_event_terms_available": False,
        "security_class_resolution_proven": False,
        "historical_event_source_completeness_proven": False,
        "event_aware_return_path_ready": False,
        "readiness_promotion_allowed": False,
        "price_series_blocker_removed": False,
        "blockers": blockers,
        "audits": [audit.to_dict() for audit in audits],
        "source_assessment": {
            "cvm_ipe": (
                "Official annual issuer-document index with reference and delivery dates; "
                "documents are unstructured and metadata is issuer-level."
            ),
            "b3_public_supplement": (
                "Current public supplement; observed rows do not prove a complete historical "
                "or revision ledger."
            ),
            "b3_up2data": (
                "Official structured corporate-action lifecycle channel exists under a "
                "commercial contract and was not adopted by this free-first audit."
            ),
        },
        "warnings": [
            "SAME_REFERENCE_DATE_DOCUMENTS_ARE_CORROBORATION_CANDIDATES_NOT_EVENT_MATCHES",
            "DOCUMENT_SUBJECTS_AND_FILES_ARE_NOT_PARSED_INTO_EVENT_TERMS",
            "CVM_IPE_METADATA_DOES_NOT_RESOLVE_SECURITY_CLASS",
            "DOCUMENT_AVAILABILITY_USES_DELIVERY_DATE_PLUS_ONE_DAY",
            "NO_READINESS_OR_PRICE_BLOCKER_CHANGE_IN_THIS_BLOCK",
        ],
    }
    required = {
        CVM_IPE_DOCUMENTS_UNSTRUCTURED,
        STRUCTURED_EVENT_HISTORY_COMPLETENESS_UNPROVEN,
    }
    if not required.issubset(blockers):
        raise RuntimeError("fail-closed CVM IPE blockers must always remain")
    Path(args.output).write_text(
        json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True),
        encoding="utf-8",
    )
    print(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True))


def _parse_samples(values: list[str]) -> tuple[tuple[str, str, int], ...]:
    samples: list[tuple[str, str, int]] = []
    companies: set[str] = set()
    tickers: set[str] = set()
    cvm_codes: set[int] = set()
    for value in values:
        parts = value.split(":")
        if len(parts) != 3:
            raise SystemExit(f"invalid sample {value!r}; expected COMPANY:TICKER:CVM_CODE")
        company = _identity(parts[0])
        ticker = _identity(parts[1])
        try:
            cvm_code = int(parts[2].strip())
        except ValueError as error:
            raise SystemExit(f"invalid CVM code in sample {value!r}") from error
        if cvm_code <= 0:
            raise SystemExit(f"invalid CVM code in sample {value!r}")
        if company in companies or ticker in tickers or cvm_code in cvm_codes:
            raise SystemExit(f"duplicate identity in sample {value!r}")
        companies.add(company)
        tickers.add(ticker)
        cvm_codes.add(cvm_code)
        samples.append((company, ticker, cvm_code))
    return tuple(samples)


def _identity(value: Any) -> str:
    normalized = "".join(character for character in str(value).upper() if character.isalnum())
    if not normalized:
        raise SystemExit("sample identity must not be blank")
    return normalized


if __name__ == "__main__":
    main()
