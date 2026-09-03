from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

BANK_EVIDENCE_NOT_POINT_IN_TIME = "BANK_EVIDENCE_NOT_POINT_IN_TIME"
PILLAR3_IPE_REVISION_HISTORY_COMPLETENESS_UNPROVEN = (
    "PILLAR3_IPE_REVISION_HISTORY_COMPLETENESS_UNPROVEN"
)
PILLAR3_NUMERIC_VALUE_EXTRACTION_UNPROVEN = "PILLAR3_NUMERIC_VALUE_EXTRACTION_UNPROVEN"
PILLAR3_METRIC_VALUE_MISSING = "PILLAR3_METRIC_VALUE_MISSING"
PILLAR3_METRIC_VALUE_AMBIGUOUS = "PILLAR3_METRIC_VALUE_AMBIGUOUS"
PILLAR3_CONFLICTING_SAME_TIMESTAMP = "PILLAR3_CONFLICTING_SAME_TIMESTAMP"

_EXPECTED_METRIC_KEYS = (
    "core_equity_tier1_ratio",
    "tier1_ratio",
    "basel_ratio",
    "leverage_ratio",
)
_ROW_ALIASES = {
    "core_equity_tier1_ratio": ("INDICE DE CAPITAL PRINCIPAL",),
    "tier1_ratio": ("INDICE DE NIVEL 1", "INDICE DE NIVEL I"),
    "basel_ratio": ("INDICE DE BASILEIA",),
    "leverage_ratio": ("RA (%)",),
}
_PERCENT_RE = re.compile(r"(?<!\d)(\d{1,3}(?:[.,]\d+)?)\s*%")


@dataclass(frozen=True, slots=True)
class Pillar3PrudentialObservation:
    prudential_reference_date: date
    available_from: datetime
    delivery_protocol: str
    version: int
    source_url: str
    pdf_sha256: str
    core_equity_tier1_ratio: float
    tier1_ratio: float
    basel_ratio: float
    leverage_ratio: float
    observed_filing_point_in_time_eligible: bool = True

    def values(self) -> dict[str, float]:
        return {key: float(getattr(self, key)) for key in _EXPECTED_METRIC_KEYS}

    def to_dict(self) -> dict[str, Any]:
        return {
            "prudential_reference_date": self.prudential_reference_date.isoformat(),
            "available_from": self.available_from.isoformat(),
            "delivery_protocol": self.delivery_protocol,
            "version": self.version,
            "source_url": self.source_url,
            "pdf_sha256": self.pdf_sha256,
            **self.values(),
            "observed_filing_point_in_time_eligible": (
                self.observed_filing_point_in_time_eligible
            ),
        }


@dataclass(frozen=True, slots=True)
class Pillar3PrudentialTimeline:
    prudential_reference_date: date
    observations: tuple[Pillar3PrudentialObservation, ...]

    def value_as_of(self, as_of: datetime) -> Pillar3PrudentialObservation | None:
        eligible = tuple(
            item for item in self.observations if item.available_from <= as_of
        )
        if not eligible:
            return None
        return eligible[-1]

    def to_dict(self) -> dict[str, Any]:
        return {
            "prudential_reference_date": self.prudential_reference_date.isoformat(),
            "observations": [item.to_dict() for item in self.observations],
        }


@dataclass(frozen=True, slots=True)
class Pillar3NumericValueAudit:
    timelines: tuple[Pillar3PrudentialTimeline, ...]
    blockers: tuple[str, ...]
    numeric_extraction_contract_ready: bool
    bank_evidence_point_in_time_ready: bool = False
    readiness_promotion_allowed: bool = False
    schema_version: str = "0.1"

    @property
    def effect(self) -> str:
        if self.numeric_extraction_contract_ready:
            return "pillar3_numeric_extraction_ready_bank_readiness_unchanged"
        return "diagnostic_only_pillar3_numeric_values_no_bank_readiness_change"

    def timeline_for(self, reference_date: date) -> Pillar3PrudentialTimeline | None:
        return next(
            (
                timeline
                for timeline in self.timelines
                if timeline.prudential_reference_date == reference_date
            ),
            None,
        )

    def value_as_of(
        self,
        *,
        reference_date: date,
        as_of: datetime,
    ) -> Pillar3PrudentialObservation | None:
        timeline = self.timeline_for(reference_date)
        return None if timeline is None else timeline.value_as_of(as_of)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "effect": self.effect,
            "timelines": [timeline.to_dict() for timeline in self.timelines],
            "blockers": list(self.blockers),
            "numeric_extraction_contract_ready": self.numeric_extraction_contract_ready,
            "bank_evidence_point_in_time_ready": self.bank_evidence_point_in_time_ready,
            "readiness_promotion_allowed": self.readiness_promotion_allowed,
        }


def extract_pillar3_prudential_observation(
    *,
    prudential_reference_date: date,
    available_from: datetime,
    delivery_protocol: str,
    version: int,
    source_url: str,
    pdf_sha256: str,
    page_texts: Sequence[str],
) -> Pillar3PrudentialObservation:
    if not delivery_protocol.strip():
        raise ValueError("delivery protocol must not be empty")
    if version <= 0:
        raise ValueError("version must be positive")
    if not source_url.startswith("https://"):
        raise ValueError("source URL must use HTTPS")
    if not re.fullmatch(r"[0-9a-f]{64}", pdf_sha256):
        raise ValueError("PDF SHA256 must be a lowercase 64-character hex digest")
    if not page_texts:
        raise ValueError("page texts must not be empty")

    extracted: dict[str, float] = {}
    missing: list[str] = []
    ambiguous: list[str] = []

    for metric_key in _EXPECTED_METRIC_KEYS:
        candidates = _metric_row_candidates(
            page_texts,
            aliases=_ROW_ALIASES[metric_key],
        )
        if not candidates:
            missing.append(metric_key)
            continue
        unique_rows = set(candidates)
        if len(unique_rows) != 1:
            ambiguous.append(metric_key)
            continue
        extracted[metric_key] = next(iter(unique_rows))[0] / 100.0

    if missing or ambiguous:
        details = []
        if missing:
            details.append(f"missing={','.join(sorted(missing))}")
        if ambiguous:
            details.append(f"ambiguous={','.join(sorted(ambiguous))}")
        raise ValueError("Pillar 3 metric extraction failed: " + "; ".join(details))

    return Pillar3PrudentialObservation(
        prudential_reference_date=prudential_reference_date,
        available_from=available_from,
        delivery_protocol=delivery_protocol,
        version=version,
        source_url=source_url,
        pdf_sha256=pdf_sha256,
        core_equity_tier1_ratio=extracted["core_equity_tier1_ratio"],
        tier1_ratio=extracted["tier1_ratio"],
        basel_ratio=extracted["basel_ratio"],
        leverage_ratio=extracted["leverage_ratio"],
    )


def audit_pillar3_numeric_values(
    observations: Iterable[Pillar3PrudentialObservation],
    *,
    extraction_failures: Iterable[str] = (),
) -> Pillar3NumericValueAudit:
    rows = tuple(observations)
    blockers = {
        BANK_EVIDENCE_NOT_POINT_IN_TIME,
        PILLAR3_IPE_REVISION_HISTORY_COMPLETENESS_UNPROVEN,
    }
    failures = tuple(extraction_failures)
    if failures:
        blockers.add(PILLAR3_NUMERIC_VALUE_EXTRACTION_UNPROVEN)
        if any("missing=" in item for item in failures):
            blockers.add(PILLAR3_METRIC_VALUE_MISSING)
        if any("ambiguous=" in item for item in failures):
            blockers.add(PILLAR3_METRIC_VALUE_AMBIGUOUS)

    grouped: dict[date, list[Pillar3PrudentialObservation]] = {}
    for observation in rows:
        grouped.setdefault(observation.prudential_reference_date, []).append(observation)

    timelines = []
    conflicting_same_timestamp = False
    for reference_date, group in sorted(grouped.items()):
        ordered = tuple(
            sorted(
                group,
                key=lambda item: (
                    item.available_from,
                    item.version,
                    item.delivery_protocol,
                ),
            )
        )
        _ensure_unique_protocols(ordered)
        if _has_conflicting_same_timestamp(ordered):
            conflicting_same_timestamp = True
        timelines.append(
            Pillar3PrudentialTimeline(
                prudential_reference_date=reference_date,
                observations=ordered,
            )
        )

    if conflicting_same_timestamp:
        blockers.add(PILLAR3_CONFLICTING_SAME_TIMESTAMP)
        blockers.add(PILLAR3_NUMERIC_VALUE_EXTRACTION_UNPROVEN)

    numeric_ready = bool(rows) and not failures and not conflicting_same_timestamp
    return Pillar3NumericValueAudit(
        timelines=tuple(timelines),
        blockers=tuple(sorted(blockers)),
        numeric_extraction_contract_ready=numeric_ready,
    )


def _metric_row_candidates(
    page_texts: Sequence[str],
    *,
    aliases: Sequence[str],
) -> tuple[tuple[float, ...], ...]:
    candidates = []
    normalized_aliases = tuple(_normalize(alias) for alias in aliases)
    for page_text in page_texts:
        for raw_line in page_text.splitlines():
            line = " ".join(raw_line.split())
            if not line:
                continue
            normalized = _normalize(line)
            if not any(normalized.startswith(alias) for alias in normalized_aliases):
                continue
            percentages = tuple(_percentages(line))
            if len(percentages) == 5:
                candidates.append(percentages)
    return tuple(candidates)


def _percentages(value: str) -> Iterable[float]:
    for token in _PERCENT_RE.findall(value):
        yield float(token.replace(",", "."))


def _normalize(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value)
    without_marks = "".join(char for char in decomposed if not unicodedata.combining(char))
    return " ".join(without_marks.upper().split())


def _ensure_unique_protocols(
    observations: Sequence[Pillar3PrudentialObservation],
) -> None:
    protocols = [item.delivery_protocol for item in observations]
    if len(protocols) != len(set(protocols)):
        raise ValueError("delivery protocols must be unique")


def _has_conflicting_same_timestamp(
    observations: Sequence[Pillar3PrudentialObservation],
) -> bool:
    grouped: dict[datetime, set[tuple[float, ...]]] = {}
    for item in observations:
        values = tuple(item.values()[key] for key in _EXPECTED_METRIC_KEYS)
        grouped.setdefault(item.available_from, set()).add(values)
    return any(len(values) > 1 for values in grouped.values())
