from __future__ import annotations

import re
import unicodedata
from dataclasses import asdict, dataclass
from datetime import date, datetime
from typing import Any

BANK_EVIDENCE_NOT_POINT_IN_TIME = "BANK_EVIDENCE_NOT_POINT_IN_TIME"
PILLAR3_IPE_REVISION_HISTORY_COMPLETENESS_UNPROVEN = (
    "PILLAR3_IPE_REVISION_HISTORY_COMPLETENESS_UNPROVEN"
)
PILLAR3_PDF_CONTENT_UNVALIDATED = "PILLAR3_PDF_CONTENT_UNVALIDATED"
PILLAR3_KM1_TABLE_NOT_FOUND = "PILLAR3_KM1_TABLE_NOT_FOUND"
PILLAR3_PRUDENTIAL_METRIC_COVERAGE_UNPROVEN = (
    "PILLAR3_PRUDENTIAL_METRIC_COVERAGE_UNPROVEN"
)
PILLAR3_PDF_REFERENCE_PERIOD_MISSING = "PILLAR3_PDF_REFERENCE_PERIOD_MISSING"
PILLAR3_PDF_REFERENCE_PERIOD_NOT_FOUND = "PILLAR3_PDF_REFERENCE_PERIOD_NOT_FOUND"

_REQUIRED_METRIC_ALIASES: dict[str, tuple[str, ...]] = {
    "core_equity_tier1_ratio": ("INDICE DE CAPITAL PRINCIPAL",),
    "tier1_ratio": (
        "INDICE DE CAPITAL NIVEL I",
        "INDICE DE CAPITAL DE NIVEL I",
        "INDICE DE CAPITAL NIVEL 1",
        "INDICE DE NIVEL I",
        "INDICE DE NIVEL 1",
    ),
    "basel_ratio": ("INDICE DE BASILEIA",),
    "leverage_ratio": (
        "RAZAO DE ALAVANCAGEM",
        "RAZAO DE ALAVANCAGEM SIMPLES",
    ),
}


@dataclass(frozen=True, slots=True)
class Pillar3PDFObservation:
    prudential_reference_date: date
    available_from: datetime
    delivery_protocol: str
    version: int
    source_url: str
    pdf_sha256: str
    size_bytes: int
    page_count: int
    extracted_text_sha256: str
    extracted_characters: int
    reference_period_detected: bool
    km1_detected: bool
    found_metric_keys: tuple[str, ...]
    missing_metric_keys: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["prudential_reference_date"] = self.prudential_reference_date.isoformat()
        payload["available_from"] = self.available_from.isoformat()
        return payload


@dataclass(frozen=True, slots=True)
class Pillar3PDFContentAudit:
    requested_reference_dates: tuple[date, ...]
    observations: tuple[Pillar3PDFObservation, ...]
    covered_reference_period_count: int
    validated_pdf_count: int
    metrics_complete_pdf_count: int
    blockers: tuple[str, ...]
    pdf_content_validated: bool
    prudential_metric_coverage_proven: bool
    revision_history_completeness_proven: bool = False
    historical_prudential_source_ready: bool = False
    bank_evidence_point_in_time_ready: bool = False
    readiness_promotion_allowed: bool = False
    effect: str = "diagnostic_only_pillar3_pdf_validation_no_bank_readiness_change"
    schema_version: str = "0.1"

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "effect": self.effect,
            "requested_reference_dates": [
                item.isoformat() for item in self.requested_reference_dates
            ],
            "observations": [item.to_dict() for item in self.observations],
            "covered_reference_period_count": self.covered_reference_period_count,
            "validated_pdf_count": self.validated_pdf_count,
            "metrics_complete_pdf_count": self.metrics_complete_pdf_count,
            "blockers": list(self.blockers),
            "pdf_content_validated": self.pdf_content_validated,
            "prudential_metric_coverage_proven": self.prudential_metric_coverage_proven,
            "revision_history_completeness_proven": self.revision_history_completeness_proven,
            "historical_prudential_source_ready": self.historical_prudential_source_ready,
            "bank_evidence_point_in_time_ready": self.bank_evidence_point_in_time_ready,
            "readiness_promotion_allowed": self.readiness_promotion_allowed,
        }


def assess_pillar3_pdf_text(
    *,
    prudential_reference_date: date,
    available_from: datetime,
    delivery_protocol: str,
    version: int,
    source_url: str,
    pdf_sha256: str,
    size_bytes: int,
    page_count: int,
    extracted_text: str,
    extracted_text_sha256: str,
) -> Pillar3PDFObservation:
    if version <= 0:
        raise ValueError("version must be positive")
    if not delivery_protocol:
        raise ValueError("delivery_protocol must not be blank")
    if not source_url.startswith("https://"):
        raise ValueError("source_url must be HTTPS")
    if not _valid_sha256(pdf_sha256) or not _valid_sha256(extracted_text_sha256):
        raise ValueError("PDF and text provenance must use SHA-256")
    if size_bytes <= 0 or page_count <= 0:
        raise ValueError("PDF size and page count must be positive")

    normalized = _normalize(extracted_text)
    found = tuple(
        key
        for key, aliases in _REQUIRED_METRIC_ALIASES.items()
        if any(alias in normalized for alias in aliases)
    )
    missing = tuple(key for key in _REQUIRED_METRIC_ALIASES if key not in found)
    return Pillar3PDFObservation(
        prudential_reference_date=prudential_reference_date,
        available_from=available_from,
        delivery_protocol=delivery_protocol,
        version=version,
        source_url=source_url,
        pdf_sha256=pdf_sha256,
        size_bytes=size_bytes,
        page_count=page_count,
        extracted_text_sha256=extracted_text_sha256,
        extracted_characters=len(extracted_text.strip()),
        reference_period_detected=_reference_period_detected(
            normalized,
            prudential_reference_date,
        ),
        km1_detected=_km1_detected(normalized),
        found_metric_keys=found,
        missing_metric_keys=missing,
    )


def audit_pillar3_pdf_content(
    *,
    requested_reference_dates: tuple[date, ...] | list[date],
    observations: tuple[Pillar3PDFObservation, ...] | list[Pillar3PDFObservation],
) -> Pillar3PDFContentAudit:
    requested = tuple(sorted(set(requested_reference_dates)))
    if not requested:
        raise ValueError("requested_reference_dates must not be empty")
    normalized_observations = tuple(
        sorted(
            observations,
            key=lambda item: (
                item.prudential_reference_date,
                item.available_from,
                item.version,
                item.delivery_protocol,
            ),
        )
    )
    if any(item.prudential_reference_date not in requested for item in normalized_observations):
        raise ValueError("observations must belong to requested_reference_dates")
    if len({item.delivery_protocol for item in normalized_observations}) != len(
        normalized_observations
    ):
        raise ValueError("delivery protocols must be unique across PDF observations")

    blockers = {
        BANK_EVIDENCE_NOT_POINT_IN_TIME,
        PILLAR3_IPE_REVISION_HISTORY_COMPLETENESS_UNPROVEN,
    }
    by_period = {
        reference_date: tuple(
            item
            for item in normalized_observations
            if item.prudential_reference_date == reference_date
        )
        for reference_date in requested
    }
    covered_count = sum(bool(items) for items in by_period.values())
    if covered_count != len(requested):
        blockers.add(PILLAR3_PDF_REFERENCE_PERIOD_MISSING)
    if any(not item.reference_period_detected for item in normalized_observations):
        blockers.add(PILLAR3_PDF_REFERENCE_PERIOD_NOT_FOUND)

    validated_count = sum(
        item.page_count > 0
        and item.extracted_characters > 0
        and item.reference_period_detected
        for item in normalized_observations
    )
    pdf_content_validated = (
        bool(normalized_observations)
        and covered_count == len(requested)
        and validated_count == len(normalized_observations)
    )
    if not pdf_content_validated:
        blockers.add(PILLAR3_PDF_CONTENT_UNVALIDATED)

    if any(not item.km1_detected for item in normalized_observations):
        blockers.add(PILLAR3_KM1_TABLE_NOT_FOUND)

    metrics_complete_count = sum(
        item.reference_period_detected and item.km1_detected and not item.missing_metric_keys
        for item in normalized_observations
    )
    metric_coverage_proven = (
        pdf_content_validated
        and metrics_complete_count == len(normalized_observations)
    )
    if not metric_coverage_proven:
        blockers.add(PILLAR3_PRUDENTIAL_METRIC_COVERAGE_UNPROVEN)

    return Pillar3PDFContentAudit(
        requested_reference_dates=requested,
        observations=normalized_observations,
        covered_reference_period_count=covered_count,
        validated_pdf_count=validated_count,
        metrics_complete_pdf_count=metrics_complete_count,
        blockers=tuple(sorted(blockers)),
        pdf_content_validated=pdf_content_validated,
        prudential_metric_coverage_proven=metric_coverage_proven,
    )


def _reference_period_detected(normalized_text: str, reference_date: date) -> bool:
    quarter = (reference_date.month - 1) // 3 + 1
    two_digit_year = reference_date.year % 100
    patterns = (
        rf"(?<![A-Z0-9]){quarter}\s*T\s*{two_digit_year:02d}(?![A-Z0-9])",
        rf"(?<![A-Z0-9]){quarter}\s*T\s*{reference_date.year}(?![A-Z0-9])",
        rf"(?<![A-Z0-9]){quarter}\s*TRIMESTRE\s*(?:DE\s*)?{reference_date.year}(?![A-Z0-9])",
    )
    return any(re.search(pattern, normalized_text) for pattern in patterns)


def _km1_detected(normalized_text: str) -> bool:
    if re.search(r"(?<![A-Z0-9])KM\s*1(?![A-Z0-9])", normalized_text):
        return True
    return (
        "INFORMACOES QUANTITATIVAS SOBRE REQUERIMENTOS PRUDENCIAIS" in normalized_text
        or "INFORMACOES QUANTITATIVAS SOBRE OS REQUERIMENTOS PRUDENCIAIS"
        in normalized_text
    ) and "INDICE DE CAPITAL PRINCIPAL" in normalized_text


def _valid_sha256(value: str) -> bool:
    return len(value) == 64 and all(
        character in "0123456789abcdefABCDEF" for character in value
    )


def _normalize(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value)
    ascii_value = "".join(
        character for character in decomposed if not unicodedata.combining(character)
    )
    return re.sub(r"[^A-Z0-9]+", " ", ascii_value.upper()).strip()
