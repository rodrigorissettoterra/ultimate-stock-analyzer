from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from ultimate_stock_analyzer.collectors.cvm_ipe import CVMIPEDocument

CVM_IPE_DOCUMENTS_UNSTRUCTURED = "CVM_IPE_DOCUMENTS_UNSTRUCTURED"
CVM_IPE_SECURITY_CLASS_SCOPE_UNPROVEN = "CVM_IPE_SECURITY_CLASS_SCOPE_UNPROVEN"
CVM_IPE_REVISION_HISTORY_COMPLETENESS_UNPROVEN = (
    "CVM_IPE_REVISION_HISTORY_COMPLETENESS_UNPROVEN"
)
STRUCTURED_EVENT_HISTORY_COMPLETENESS_UNPROVEN = (
    "STRUCTURED_EVENT_HISTORY_COMPLETENESS_UNPROVEN"
)
EVENT_APPROVAL_DATE_MISSING = "EVENT_APPROVAL_DATE_MISSING"
EVENT_DOCUMENT_REFERENCE_DATE_NOT_FOUND = "EVENT_DOCUMENT_REFERENCE_DATE_NOT_FOUND"
EVENT_DOCUMENT_NOT_AVAILABLE_BY_COM_DATE = "EVENT_DOCUMENT_NOT_AVAILABLE_BY_COM_DATE"
UNSUPPORTED_SUBSCRIPTION_RIGHTS = "UNSUPPORTED_SUBSCRIPTION_RIGHTS"

_SECTIONS = ("stockDividends", "cashDividends", "subscriptions")


@dataclass(frozen=True, slots=True)
class B3ObservedCorporateEvent:
    source_section: str
    source_index: int
    label: str
    normalized_label: str
    asset_issued: str | None
    isin_code: str | None
    approved_on: date | None
    last_date_prior: date

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_section": self.source_section,
            "source_index": self.source_index,
            "label": self.label,
            "normalized_label": self.normalized_label,
            "asset_issued": self.asset_issued,
            "isin_code": self.isin_code,
            "approved_on": self.approved_on.isoformat() if self.approved_on else None,
            "last_date_prior": self.last_date_prior.isoformat(),
        }


@dataclass(frozen=True, slots=True)
class CVMIPEEventCorroboration:
    event: B3ObservedCorporateEvent
    same_reference_date_documents: tuple[CVMIPEDocument, ...]
    available_by_com_documents: tuple[CVMIPEDocument, ...]
    blockers: tuple[str, ...]
    status: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "event": self.event.to_dict(),
            "status": self.status,
            "same_reference_date_document_count": len(self.same_reference_date_documents),
            "available_by_com_document_count": len(self.available_by_com_documents),
            "same_reference_date_documents": [
                document.to_dict() for document in self.same_reference_date_documents
            ],
            "available_by_com_documents": [
                document.to_dict() for document in self.available_by_com_documents
            ],
            "blockers": list(self.blockers),
        }


@dataclass(frozen=True, slots=True)
class CVMIPECorporateActionLedgerAudit:
    issuing_company: str
    ticker: str
    company_id: str
    start_date: date
    end_date: date
    generated_at: datetime
    source_years: tuple[int, ...]
    issuer_document_count: int
    observed_event_count: int
    observed_stock_event_count: int
    observed_cash_event_count: int
    observed_subscription_count: int
    events_with_same_reference_date_documents: int
    events_with_documents_available_by_com: int
    exact_reference_date_candidate_count: int
    corroborations: tuple[CVMIPEEventCorroboration, ...]
    blockers: tuple[str, ...]
    historical_document_archive_available: bool
    observed_event_document_corroboration_complete: bool
    observed_event_pit_document_corroboration_complete: bool
    structured_event_terms_available: bool = False
    security_class_resolution_proven: bool = False
    historical_event_source_completeness_proven: bool = False
    event_aware_return_path_ready: bool = False
    readiness_promotion_allowed: bool = False
    price_series_blocker_removed: bool = False
    effect: str = "diagnostic_only_cvm_ipe_ledger_no_readiness_change"
    schema_version: str = "0.1"

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "effect": self.effect,
            "issuing_company": self.issuing_company,
            "ticker": self.ticker,
            "company_id": self.company_id,
            "start_date": self.start_date.isoformat(),
            "end_date": self.end_date.isoformat(),
            "generated_at": self.generated_at.isoformat(),
            "source_years": list(self.source_years),
            "issuer_document_count": self.issuer_document_count,
            "observed_event_count": self.observed_event_count,
            "observed_stock_event_count": self.observed_stock_event_count,
            "observed_cash_event_count": self.observed_cash_event_count,
            "observed_subscription_count": self.observed_subscription_count,
            "events_with_same_reference_date_documents": (
                self.events_with_same_reference_date_documents
            ),
            "events_with_documents_available_by_com": (
                self.events_with_documents_available_by_com
            ),
            "exact_reference_date_candidate_count": self.exact_reference_date_candidate_count,
            "corroborations": [item.to_dict() for item in self.corroborations],
            "blockers": list(self.blockers),
            "historical_document_archive_available": self.historical_document_archive_available,
            "observed_event_document_corroboration_complete": (
                self.observed_event_document_corroboration_complete
            ),
            "observed_event_pit_document_corroboration_complete": (
                self.observed_event_pit_document_corroboration_complete
            ),
            "structured_event_terms_available": self.structured_event_terms_available,
            "security_class_resolution_proven": self.security_class_resolution_proven,
            "historical_event_source_completeness_proven": (
                self.historical_event_source_completeness_proven
            ),
            "event_aware_return_path_ready": self.event_aware_return_path_ready,
            "readiness_promotion_allowed": self.readiness_promotion_allowed,
            "price_series_blocker_removed": self.price_series_blocker_removed,
        }


def audit_cvm_ipe_corporate_action_ledger(
    *,
    issuing_company: str,
    ticker: str,
    cvm_code: int,
    b3_payload: dict[str, Any],
    documents: tuple[CVMIPEDocument, ...] | list[CVMIPEDocument],
    source_years: tuple[int, ...] | list[int],
    start_date: date,
    end_date: date,
    generated_at: datetime,
) -> CVMIPECorporateActionLedgerAudit:
    if cvm_code <= 0:
        raise ValueError("cvm_code must be positive")
    if start_date > end_date:
        raise ValueError("start_date must not be after end_date")
    company_id = f"cvm:{cvm_code}"
    issuer_documents = tuple(
        sorted(
            (document for document in documents if document.company_id == company_id),
            key=lambda document: (
                document.reference_date,
                document.delivered_on,
                document.category,
                document.document_type or "",
                document.delivery_protocol or "",
            ),
        )
    )
    wrong_identity_documents = [
        document
        for document in documents
        if document.cvm_code == cvm_code and document.company_id != company_id
    ]
    if wrong_identity_documents:
        raise ValueError("CVM IPE document company identity is inconsistent")

    events = _observed_events(
        b3_payload,
        start_date=start_date,
        end_date=end_date,
    )
    documents_by_reference_date: dict[date, list[CVMIPEDocument]] = {}
    for document in issuer_documents:
        documents_by_reference_date.setdefault(document.reference_date, []).append(document)

    corroborations: list[CVMIPEEventCorroboration] = []
    audit_blockers = {
        CVM_IPE_DOCUMENTS_UNSTRUCTURED,
        CVM_IPE_SECURITY_CLASS_SCOPE_UNPROVEN,
        CVM_IPE_REVISION_HISTORY_COMPLETENESS_UNPROVEN,
        STRUCTURED_EVENT_HISTORY_COMPLETENESS_UNPROVEN,
    }
    for event in events:
        blockers: set[str] = set()
        candidates: tuple[CVMIPEDocument, ...] = ()
        if event.approved_on is None:
            blockers.add(EVENT_APPROVAL_DATE_MISSING)
        else:
            candidates = tuple(documents_by_reference_date.get(event.approved_on, ()))
            if not candidates:
                blockers.add(EVENT_DOCUMENT_REFERENCE_DATE_NOT_FOUND)
        available_by_com = tuple(
            document
            for document in candidates
            if document.available_from.date() <= event.last_date_prior
        )
        if candidates and not available_by_com:
            blockers.add(EVENT_DOCUMENT_NOT_AVAILABLE_BY_COM_DATE)
        if event.source_section == "subscriptions":
            blockers.add(UNSUPPORTED_SUBSCRIPTION_RIGHTS)
        audit_blockers.update(blockers)
        status = (
            "SAME_REFERENCE_DATE_DOCUMENTS_FOUND"
            if candidates
            else "NO_DOCUMENT_CORROBORATION"
        )
        corroborations.append(
            CVMIPEEventCorroboration(
                event=event,
                same_reference_date_documents=candidates,
                available_by_com_documents=available_by_com,
                blockers=tuple(sorted(blockers)),
                status=status,
            )
        )

    observed_count = len(corroborations)
    same_date_count = sum(bool(item.same_reference_date_documents) for item in corroborations)
    pit_count = sum(bool(item.available_by_com_documents) for item in corroborations)
    normalized_source_years = tuple(sorted(set(source_years)))
    expected_years = set(range(start_date.year, end_date.year + 1))
    archive_available = bool(issuer_documents) and expected_years.issubset(normalized_source_years)
    return CVMIPECorporateActionLedgerAudit(
        issuing_company=_identity(issuing_company),
        ticker=_identity(ticker),
        company_id=company_id,
        start_date=start_date,
        end_date=end_date,
        generated_at=generated_at,
        source_years=normalized_source_years,
        issuer_document_count=len(issuer_documents),
        observed_event_count=observed_count,
        observed_stock_event_count=sum(
            item.event.source_section == "stockDividends" for item in corroborations
        ),
        observed_cash_event_count=sum(
            item.event.source_section == "cashDividends" for item in corroborations
        ),
        observed_subscription_count=sum(
            item.event.source_section == "subscriptions" for item in corroborations
        ),
        events_with_same_reference_date_documents=same_date_count,
        events_with_documents_available_by_com=pit_count,
        exact_reference_date_candidate_count=sum(
            len(item.same_reference_date_documents) for item in corroborations
        ),
        corroborations=tuple(corroborations),
        blockers=tuple(sorted(audit_blockers)),
        historical_document_archive_available=archive_available,
        observed_event_document_corroboration_complete=(
            observed_count > 0 and same_date_count == observed_count
        ),
        observed_event_pit_document_corroboration_complete=(
            observed_count > 0 and pit_count == observed_count
        ),
    )


def _observed_events(
    payload: dict[str, Any],
    *,
    start_date: date,
    end_date: date,
) -> tuple[B3ObservedCorporateEvent, ...]:
    events: list[B3ObservedCorporateEvent] = []
    for section in _SECTIONS:
        rows = payload.get(section) or []
        if not isinstance(rows, list):
            raise TypeError(f"B3 {section} must be a list")
        for index, row in enumerate(rows):
            if not isinstance(row, dict):
                raise TypeError(f"B3 {section}[{index}] must be an object")
            last_date_prior = _parse_date(row.get("lastDatePrior"))
            if last_date_prior is None or not start_date <= last_date_prior <= end_date:
                continue
            label = str(row.get("label") or "").strip()
            events.append(
                B3ObservedCorporateEvent(
                    source_section=section,
                    source_index=index,
                    label=label,
                    normalized_label=_normalize_label(label),
                    asset_issued=_optional_text(row.get("assetIssued")),
                    isin_code=_optional_text(row.get("isinCode")),
                    approved_on=_parse_date(row.get("approvedOn")),
                    last_date_prior=last_date_prior,
                )
            )
    return tuple(
        sorted(
            events,
            key=lambda item: (
                item.last_date_prior,
                item.source_section,
                item.source_index,
            ),
        )
    )


def _parse_date(value: Any) -> date | None:
    text = _optional_text(value)
    if text is None:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        parts = text.split("/")
        if len(parts) == 3:
            try:
                day, month, year = (int(part) for part in parts)
                return date(year, month, day)
            except ValueError:
                pass
    return None


def _normalize_label(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value)
    ascii_value = "".join(
        character for character in decomposed if not unicodedata.combining(character)
    )
    return re.sub(r"[^A-Z0-9]+", "_", ascii_value.upper()).strip("_")


def _identity(value: str) -> str:
    normalized = "".join(character for character in value.upper() if character.isalnum())
    if not normalized:
        raise ValueError("identity must not be blank")
    return normalized


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
