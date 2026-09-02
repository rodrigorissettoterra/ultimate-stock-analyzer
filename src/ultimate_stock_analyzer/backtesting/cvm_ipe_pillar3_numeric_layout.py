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
PILLAR3_NUMERIC_LAYOUT_UNPROVEN = "PILLAR3_NUMERIC_LAYOUT_UNPROVEN"
PILLAR3_METRIC_CONTEXT_NOT_FOUND = "PILLAR3_METRIC_CONTEXT_NOT_FOUND"
PILLAR3_METRIC_NUMERIC_CANDIDATE_NOT_FOUND = "PILLAR3_METRIC_NUMERIC_CANDIDATE_NOT_FOUND"

_METRIC_ALIASES: dict[str, tuple[str, ...]] = {
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
_PERCENT_TOKEN = re.compile(r"(?<!\d)(\d{1,3}(?:[.,]\d{1,4})?)\s*%")
_DECIMAL_TOKEN = re.compile(r"(?<!\d)(\d{1,3}[.,]\d{1,4})(?!\d)")


@dataclass(frozen=True, slots=True)
class Pillar3MetricLayoutEvidence:
    metric_key: str
    page_number: int
    matched_label: str
    context: str
    numeric_tokens: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class Pillar3DocumentLayoutEvidence:
    prudential_reference_date: date
    available_from: datetime
    delivery_protocol: str
    version: int
    source_url: str
    pdf_sha256: str
    page_count: int
    metric_evidence: tuple[Pillar3MetricLayoutEvidence, ...]
    missing_metric_keys: tuple[str, ...]
    metrics_without_numeric_candidates: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "prudential_reference_date": self.prudential_reference_date.isoformat(),
            "available_from": self.available_from.isoformat(),
            "delivery_protocol": self.delivery_protocol,
            "version": self.version,
            "source_url": self.source_url,
            "pdf_sha256": self.pdf_sha256,
            "page_count": self.page_count,
            "metric_evidence": [item.to_dict() for item in self.metric_evidence],
            "missing_metric_keys": list(self.missing_metric_keys),
            "metrics_without_numeric_candidates": list(
                self.metrics_without_numeric_candidates
            ),
        }


@dataclass(frozen=True, slots=True)
class Pillar3NumericLayoutAudit:
    documents: tuple[Pillar3DocumentLayoutEvidence, ...]
    blockers: tuple[str, ...]
    all_metric_contexts_observed: bool
    all_metric_contexts_have_numeric_candidates: bool
    numeric_extraction_contract_ready: bool = False
    bank_evidence_point_in_time_ready: bool = False
    readiness_promotion_allowed: bool = False
    effect: str = "diagnostic_only_pillar3_numeric_layout_no_readiness_change"
    schema_version: str = "0.1"

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "effect": self.effect,
            "documents": [item.to_dict() for item in self.documents],
            "blockers": list(self.blockers),
            "all_metric_contexts_observed": self.all_metric_contexts_observed,
            "all_metric_contexts_have_numeric_candidates": (
                self.all_metric_contexts_have_numeric_candidates
            ),
            "numeric_extraction_contract_ready": self.numeric_extraction_contract_ready,
            "bank_evidence_point_in_time_ready": self.bank_evidence_point_in_time_ready,
            "readiness_promotion_allowed": self.readiness_promotion_allowed,
        }


def inspect_pillar3_document_layout(
    *,
    prudential_reference_date: date,
    available_from: datetime,
    delivery_protocol: str,
    version: int,
    source_url: str,
    pdf_sha256: str,
    page_texts: tuple[str, ...] | list[str],
    context_radius_lines: int = 10,
) -> Pillar3DocumentLayoutEvidence:
    if context_radius_lines < 1 or context_radius_lines > 20:
        raise ValueError("context_radius_lines must be between 1 and 20")
    if version <= 0 or not delivery_protocol:
        raise ValueError("version and delivery_protocol are required")
    if len(pdf_sha256) != 64:
        raise ValueError("pdf_sha256 must be a SHA-256 hex digest")
    if not page_texts:
        raise ValueError("page_texts must not be empty")

    evidence: list[Pillar3MetricLayoutEvidence] = []
    missing: list[str] = []
    without_numbers: list[str] = []
    for metric_key, aliases in _METRIC_ALIASES.items():
        match = _find_metric_context(
            metric_key=metric_key,
            aliases=aliases,
            page_texts=page_texts,
            context_radius_lines=context_radius_lines,
        )
        if match is None:
            missing.append(metric_key)
            continue
        evidence.append(match)
        if not match.numeric_tokens:
            without_numbers.append(metric_key)

    return Pillar3DocumentLayoutEvidence(
        prudential_reference_date=prudential_reference_date,
        available_from=available_from,
        delivery_protocol=delivery_protocol,
        version=version,
        source_url=source_url,
        pdf_sha256=pdf_sha256,
        page_count=len(page_texts),
        metric_evidence=tuple(evidence),
        missing_metric_keys=tuple(missing),
        metrics_without_numeric_candidates=tuple(without_numbers),
    )


def audit_pillar3_numeric_layout(
    documents: tuple[Pillar3DocumentLayoutEvidence, ...]
    | list[Pillar3DocumentLayoutEvidence],
) -> Pillar3NumericLayoutAudit:
    normalized = tuple(
        sorted(
            documents,
            key=lambda item: (
                item.prudential_reference_date,
                item.available_from,
                item.version,
                item.delivery_protocol,
            ),
        )
    )
    if not normalized:
        raise ValueError("documents must not be empty")
    if len({item.delivery_protocol for item in normalized}) != len(normalized):
        raise ValueError("delivery protocols must be unique")

    blockers = {
        BANK_EVIDENCE_NOT_POINT_IN_TIME,
        PILLAR3_IPE_REVISION_HISTORY_COMPLETENESS_UNPROVEN,
        PILLAR3_NUMERIC_LAYOUT_UNPROVEN,
    }
    all_contexts = all(not item.missing_metric_keys for item in normalized)
    all_numeric = all(
        not item.missing_metric_keys and not item.metrics_without_numeric_candidates
        for item in normalized
    )
    if not all_contexts:
        blockers.add(PILLAR3_METRIC_CONTEXT_NOT_FOUND)
    if not all_numeric:
        blockers.add(PILLAR3_METRIC_NUMERIC_CANDIDATE_NOT_FOUND)

    return Pillar3NumericLayoutAudit(
        documents=normalized,
        blockers=tuple(sorted(blockers)),
        all_metric_contexts_observed=all_contexts,
        all_metric_contexts_have_numeric_candidates=all_numeric,
    )


def _find_metric_context(
    *,
    metric_key: str,
    aliases: tuple[str, ...],
    page_texts: tuple[str, ...] | list[str],
    context_radius_lines: int,
) -> Pillar3MetricLayoutEvidence | None:
    fallback: Pillar3MetricLayoutEvidence | None = None
    for page_index, page_text in enumerate(page_texts):
        lines = [line.strip() for line in page_text.splitlines() if line.strip()]
        normalized_lines = [_normalize(line) for line in lines]
        for line_index, normalized_line in enumerate(normalized_lines):
            matched_alias = next(
                (alias for alias in aliases if alias in normalized_line),
                None,
            )
            if matched_alias is None:
                continue
            start = max(0, line_index - context_radius_lines)
            end = min(len(lines), line_index + context_radius_lines + 1)
            context = " | ".join(lines[start:end])[:1800]
            candidate = Pillar3MetricLayoutEvidence(
                metric_key=metric_key,
                page_number=page_index + 1,
                matched_label=matched_alias,
                context=context,
                numeric_tokens=_numeric_tokens(context),
            )
            if candidate.numeric_tokens:
                return candidate
            if fallback is None:
                fallback = candidate
    return fallback


def _numeric_tokens(context: str) -> tuple[str, ...]:
    percent_tokens = [
        match.group(1).replace(",", ".") for match in _PERCENT_TOKEN.finditer(context)
    ]
    if percent_tokens:
        return tuple(dict.fromkeys(percent_tokens))
    decimal_tokens = [
        match.group(1).replace(",", ".") for match in _DECIMAL_TOKEN.finditer(context)
    ]
    return tuple(dict.fromkeys(decimal_tokens))


def _normalize(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value)
    ascii_value = "".join(
        character for character in decomposed if not unicodedata.combining(character)
    )
    return re.sub(r"[^A-Z0-9]+", " ", ascii_value.upper()).strip()
