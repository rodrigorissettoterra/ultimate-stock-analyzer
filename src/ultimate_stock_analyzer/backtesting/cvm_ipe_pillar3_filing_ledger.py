from __future__ import annotations

import re
import unicodedata
from dataclasses import asdict, dataclass
from datetime import date, datetime
from typing import Any

from ultimate_stock_analyzer.collectors.cvm_ipe import CVMIPEDocument

BANK_EVIDENCE_NOT_POINT_IN_TIME = "BANK_EVIDENCE_NOT_POINT_IN_TIME"
PILLAR3_IPE_PERIOD_FILING_NOT_FOUND = "PILLAR3_IPE_PERIOD_FILING_NOT_FOUND"
PILLAR3_IPE_PERIOD_TOKEN_MISSING = "PILLAR3_IPE_PERIOD_TOKEN_MISSING"
PILLAR3_IPE_PERIOD_TOKEN_AMBIGUOUS = "PILLAR3_IPE_PERIOD_TOKEN_AMBIGUOUS"
PILLAR3_IPE_DOWNLOAD_URL_MISSING = "PILLAR3_IPE_DOWNLOAD_URL_MISSING"
PILLAR3_IPE_REVISION_HISTORY_COMPLETENESS_UNPROVEN = (
    "PILLAR3_IPE_REVISION_HISTORY_COMPLETENESS_UNPROVEN"
)
PILLAR3_PDF_CONTENT_UNVALIDATED = "PILLAR3_PDF_CONTENT_UNVALIDATED"
PILLAR3_PRUDENTIAL_METRIC_COVERAGE_UNPROVEN = (
    "PILLAR3_PRUDENTIAL_METRIC_COVERAGE_UNPROVEN"
)

_QUARTER_TOKEN = re.compile(r"(?<![A-Z0-9])([1-4])\s*T\s*(\d{2}|\d{4})(?![A-Z0-9])")


@dataclass(frozen=True, slots=True)
class CVMIPEArchiveSnapshot:
    source_year: int
    source_url: str
    sha256: str
    size_bytes: int


@dataclass(frozen=True, slots=True)
class Pillar3FilingObservation:
    period_token: str
    prudential_reference_date: date
    document: CVMIPEDocument

    def to_dict(self) -> dict[str, Any]:
        return {
            "period_token": self.period_token,
            "prudential_reference_date": self.prudential_reference_date.isoformat(),
            "document": self.document.to_dict(),
        }


@dataclass(frozen=True, slots=True)
class Pillar3PeriodTimeline:
    prudential_reference_date: date
    filings: tuple[Pillar3FilingObservation, ...]
    earliest_observed_available_from: datetime | None
    latest_observed_available_from: datetime | None
    observed_delivery_protocols: tuple[str, ...]
    observed_versions: tuple[int, ...]
    blockers: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "prudential_reference_date": self.prudential_reference_date.isoformat(),
            "filing_count": len(self.filings),
            "earliest_observed_available_from": (
                self.earliest_observed_available_from.isoformat()
                if self.earliest_observed_available_from
                else None
            ),
            "latest_observed_available_from": (
                self.latest_observed_available_from.isoformat()
                if self.latest_observed_available_from
                else None
            ),
            "observed_delivery_protocols": list(self.observed_delivery_protocols),
            "observed_versions": list(self.observed_versions),
            "filings": [item.to_dict() for item in self.filings],
            "blockers": list(self.blockers),
        }


@dataclass(frozen=True, slots=True)
class CVMIPEPillar3FilingLedgerAudit:
    company_id: str
    cvm_code: int
    generated_at: datetime
    requested_reference_dates: tuple[date, ...]
    source_archives: tuple[CVMIPEArchiveSnapshot, ...]
    issuer_document_count: int
    pillar3_candidate_count: int
    mapped_pillar3_candidate_count: int
    unmapped_pillar3_candidate_count: int
    covered_reference_period_count: int
    periods_with_multiple_observed_filings: int
    timelines: tuple[Pillar3PeriodTimeline, ...]
    blockers: tuple[str, ...]
    observed_filing_timeline_available: bool
    multiple_observed_filings_present: bool
    revision_history_completeness_proven: bool = False
    pdf_content_validated: bool = False
    prudential_metric_coverage_proven: bool = False
    historical_prudential_source_ready: bool = False
    bank_evidence_point_in_time_ready: bool = False
    readiness_promotion_allowed: bool = False
    effect: str = "diagnostic_only_cvm_ipe_pillar3_ledger_no_readiness_change"
    schema_version: str = "0.1"

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "effect": self.effect,
            "company_id": self.company_id,
            "cvm_code": self.cvm_code,
            "generated_at": self.generated_at.isoformat(),
            "requested_reference_dates": [
                item.isoformat() for item in self.requested_reference_dates
            ],
            "source_archives": [asdict(item) for item in self.source_archives],
            "issuer_document_count": self.issuer_document_count,
            "pillar3_candidate_count": self.pillar3_candidate_count,
            "mapped_pillar3_candidate_count": self.mapped_pillar3_candidate_count,
            "unmapped_pillar3_candidate_count": self.unmapped_pillar3_candidate_count,
            "covered_reference_period_count": self.covered_reference_period_count,
            "periods_with_multiple_observed_filings": (
                self.periods_with_multiple_observed_filings
            ),
            "timelines": [item.to_dict() for item in self.timelines],
            "blockers": list(self.blockers),
            "observed_filing_timeline_available": self.observed_filing_timeline_available,
            "multiple_observed_filings_present": self.multiple_observed_filings_present,
            "revision_history_completeness_proven": self.revision_history_completeness_proven,
            "pdf_content_validated": self.pdf_content_validated,
            "prudential_metric_coverage_proven": self.prudential_metric_coverage_proven,
            "historical_prudential_source_ready": self.historical_prudential_source_ready,
            "bank_evidence_point_in_time_ready": self.bank_evidence_point_in_time_ready,
            "readiness_promotion_allowed": self.readiness_promotion_allowed,
        }


def audit_cvm_ipe_pillar3_filing_ledger(
    *,
    cvm_code: int,
    documents: tuple[CVMIPEDocument, ...] | list[CVMIPEDocument],
    source_archives: tuple[CVMIPEArchiveSnapshot, ...] | list[CVMIPEArchiveSnapshot],
    requested_reference_dates: tuple[date, ...] | list[date],
    generated_at: datetime,
) -> CVMIPEPillar3FilingLedgerAudit:
    if cvm_code <= 0:
        raise ValueError("cvm_code must be positive")
    requested_dates = tuple(sorted(set(requested_reference_dates)))
    if not requested_dates:
        raise ValueError("requested_reference_dates must not be empty")
    if any(item.month != 12 or item.day != 31 for item in requested_dates):
        raise ValueError(
            "this diagnostic currently accepts annual 31 December reference dates only"
        )

    normalized_archives = tuple(sorted(source_archives, key=lambda item: item.source_year))
    if not normalized_archives:
        raise ValueError("source_archives must not be empty")
    if len({item.source_year for item in normalized_archives}) != len(normalized_archives):
        raise ValueError("source_archives must contain at most one snapshot per source year")
    if any(not _valid_archive_snapshot(item) for item in normalized_archives):
        raise ValueError("source archive provenance must include SHA-256 and positive size")

    company_id = f"cvm:{cvm_code}"
    issuer_documents = tuple(
        sorted(
            (document for document in documents if document.company_id == company_id),
            key=_document_sort_key,
        )
    )
    candidates = tuple(document for document in issuer_documents if _is_pillar3_candidate(document))

    mapped: list[Pillar3FilingObservation] = []
    missing_token_count = 0
    ambiguous_token_count = 0
    for document in candidates:
        parsed = _prudential_period_from_document(document)
        if parsed is None:
            missing_token_count += 1
            continue
        if len(parsed) != 1:
            ambiguous_token_count += 1
            continue
        period_token, reference_date = parsed[0]
        mapped.append(
            Pillar3FilingObservation(
                period_token=period_token,
                prudential_reference_date=reference_date,
                document=document,
            )
        )

    mapped_observations = tuple(
        sorted(
            mapped,
            key=lambda item: (
                item.prudential_reference_date,
                *_document_sort_key(item.document),
            ),
        )
    )
    by_period: dict[date, list[Pillar3FilingObservation]] = {}
    for observation in mapped_observations:
        by_period.setdefault(observation.prudential_reference_date, []).append(observation)

    blockers = {
        BANK_EVIDENCE_NOT_POINT_IN_TIME,
        PILLAR3_IPE_REVISION_HISTORY_COMPLETENESS_UNPROVEN,
        PILLAR3_PDF_CONTENT_UNVALIDATED,
        PILLAR3_PRUDENTIAL_METRIC_COVERAGE_UNPROVEN,
    }
    if missing_token_count:
        blockers.add(PILLAR3_IPE_PERIOD_TOKEN_MISSING)
    if ambiguous_token_count:
        blockers.add(PILLAR3_IPE_PERIOD_TOKEN_AMBIGUOUS)

    timelines: list[Pillar3PeriodTimeline] = []
    for reference_date in requested_dates:
        filings = tuple(by_period.get(reference_date, ()))
        period_blockers: set[str] = set()
        if not filings:
            period_blockers.add(PILLAR3_IPE_PERIOD_FILING_NOT_FOUND)
        if any(item.document.download_url is None for item in filings):
            period_blockers.add(PILLAR3_IPE_DOWNLOAD_URL_MISSING)
        blockers.update(period_blockers)
        available = tuple(item.document.available_from for item in filings)
        timelines.append(
            Pillar3PeriodTimeline(
                prudential_reference_date=reference_date,
                filings=filings,
                earliest_observed_available_from=min(available) if available else None,
                latest_observed_available_from=max(available) if available else None,
                observed_delivery_protocols=tuple(
                    sorted(
                        {
                            protocol
                            for item in filings
                            if (protocol := item.document.delivery_protocol) is not None
                        }
                    )
                ),
                observed_versions=tuple(
                    sorted(
                        {
                            version
                            for item in filings
                            if (version := item.document.version) is not None
                        }
                    )
                ),
                blockers=tuple(sorted(period_blockers)),
            )
        )

    timeline_tuple = tuple(timelines)
    covered_count = sum(bool(item.filings) for item in timeline_tuple)
    multiple_count = sum(len(item.filings) > 1 for item in timeline_tuple)
    timeline_available = (
        covered_count == len(requested_dates)
        and all(
            item.document.delivery_protocol is not None and item.document.download_url is not None
            for timeline in timeline_tuple
            for item in timeline.filings
        )
    )
    return CVMIPEPillar3FilingLedgerAudit(
        company_id=company_id,
        cvm_code=cvm_code,
        generated_at=generated_at,
        requested_reference_dates=requested_dates,
        source_archives=normalized_archives,
        issuer_document_count=len(issuer_documents),
        pillar3_candidate_count=len(candidates),
        mapped_pillar3_candidate_count=len(mapped_observations),
        unmapped_pillar3_candidate_count=missing_token_count + ambiguous_token_count,
        covered_reference_period_count=covered_count,
        periods_with_multiple_observed_filings=multiple_count,
        timelines=timeline_tuple,
        blockers=tuple(sorted(blockers)),
        observed_filing_timeline_available=timeline_available,
        multiple_observed_filings_present=multiple_count > 0,
    )


def _valid_archive_snapshot(snapshot: CVMIPEArchiveSnapshot) -> bool:
    if snapshot.size_bytes <= 0 or len(snapshot.sha256) != 64:
        return False
    return all(character in "0123456789abcdefABCDEF" for character in snapshot.sha256)


def _is_pillar3_candidate(document: CVMIPEDocument) -> bool:
    text = " ".join(
        item
        for item in (
            document.category,
            document.document_type,
            document.species,
            document.subject,
        )
        if item
    )
    normalized = _normalize(text)
    return "PILAR 3" in normalized or "PILAR III" in normalized


def _prudential_period_from_document(
    document: CVMIPEDocument,
) -> tuple[tuple[str, date], ...] | None:
    if document.subject is None:
        return None
    normalized = _normalize(document.subject)
    matches = _QUARTER_TOKEN.findall(normalized)
    if not matches:
        return None
    parsed: list[tuple[str, date]] = []
    for quarter_text, year_text in matches:
        quarter = int(quarter_text)
        year = int(year_text)
        if len(year_text) == 2:
            year += 2000
        month = quarter * 3
        day = 31 if month in {3, 12} else 30
        parsed.append((f"{quarter}T{year % 100:02d}", date(year, month, day)))
    return tuple(dict.fromkeys(parsed))


def _document_sort_key(document: CVMIPEDocument) -> tuple[Any, ...]:
    return (
        document.delivered_on,
        document.available_from,
        document.reference_date,
        document.version or 0,
        document.delivery_protocol or "",
        document.subject or "",
    )


def _normalize(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value)
    ascii_value = "".join(
        character for character in decomposed if not unicodedata.combining(character)
    )
    return re.sub(r"[^A-Z0-9]+", " ", ascii_value.upper()).strip()
