from __future__ import annotations

import csv
import hashlib
import io
import re
import unicodedata
import zipfile
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any

FRE_STRUCTURED_ACTIVITY_FIELD_UNAVAILABLE = "FRE_STRUCTURED_ACTIVITY_FIELD_UNAVAILABLE"
FRE_ISSUER_COVERAGE_INCOMPLETE = "FRE_ISSUER_COVERAGE_INCOMPLETE"
FRE_FILING_TIMING_FIELDS_UNPROVEN = "FRE_FILING_TIMING_FIELDS_UNPROVEN"
FRE_ACTIVITY_TO_MODEL_MAPPING_UNPROVEN = "FRE_ACTIVITY_TO_MODEL_MAPPING_UNPROVEN"
HISTORICAL_MODEL_APPLICABILITY_UNPROVEN = "HISTORICAL_MODEL_APPLICABILITY_UNPROVEN"

_ACTIVITY_TOKENS = (
    "atividade",
    "negocio",
    "objeto",
    "setor",
    "segmento",
    "cnae",
    "produto",
    "servico",
)
_FILING_DATE_TOKENS = (
    "dt_receb",
    "data_receb",
    "dt_entrega",
    "data_entrega",
    "dt_refer",
    "data_refer",
    "dt_apresent",
    "data_apresent",
)
_REVISION_TOKENS = (
    "versao",
    "protocolo",
)
_CVM_CODE_COLUMNS = ("cd_cvm", "codigo_cvm", "cod_cvm")


@dataclass(frozen=True, slots=True)
class FRECandidateField:
    member_name: str
    column_name: str
    matched_tokens: tuple[str, ...]
    issuer_row_count: int
    nonempty_value_count: int
    sample_values: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["matched_tokens"] = list(self.matched_tokens)
        payload["sample_values"] = list(self.sample_values)
        return payload


@dataclass(frozen=True, slots=True)
class FREHistoricalApplicabilitySourceAudit:
    collected_at: datetime
    delivery_year: int
    source_url: str
    requested_cvm_codes: tuple[int, ...]
    archive_sha256: str
    archive_size_bytes: int
    member_count: int
    csv_member_count: int
    issuer_codes_observed: tuple[int, ...]
    issuer_coverage_complete: bool
    activity_candidate_fields: tuple[FRECandidateField, ...]
    timing_candidate_fields: tuple[FRECandidateField, ...]
    revision_candidate_fields: tuple[FRECandidateField, ...]
    structured_activity_fields_found: bool
    filing_timing_fields_found: bool
    revision_metadata_fields_found: bool
    deterministic_model_routing_supported: bool
    sector_routing_point_in_time_ready: bool
    readiness_promotion_allowed: bool
    blockers: tuple[str, ...]
    effect: str = "diagnostic_only_fre_historical_applicability_source_no_routing_change"
    schema_version: str = "0.2"

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["collected_at"] = self.collected_at.isoformat()
        payload["requested_cvm_codes"] = list(self.requested_cvm_codes)
        payload["issuer_codes_observed"] = list(self.issuer_codes_observed)
        payload["activity_candidate_fields"] = [
            item.to_dict() for item in self.activity_candidate_fields
        ]
        payload["timing_candidate_fields"] = [
            item.to_dict() for item in self.timing_candidate_fields
        ]
        payload["revision_candidate_fields"] = [
            item.to_dict() for item in self.revision_candidate_fields
        ]
        payload["blockers"] = list(self.blockers)
        return payload


def audit_fre_historical_applicability_source(
    *,
    archive_content: bytes,
    collected_at: datetime,
    delivery_year: int,
    source_url: str,
    requested_cvm_codes: tuple[int, ...] | list[int],
) -> FREHistoricalApplicabilitySourceAudit:
    """Inspect one official annual FRE archive for historical model-routing evidence.

    This is discovery-only. Activity semantics, actual filing availability and revision behavior
    must be validated independently before any historical model route can become admissible.
    """
    if delivery_year < 2010:
        raise ValueError("FRE public archives are expected from 2010 onward")
    if not source_url.startswith("https://dados.cvm.gov.br/"):
        raise ValueError("FRE source_url must use the official CVM open-data HTTPS host")
    if not archive_content.startswith(b"PK"):
        raise ValueError("FRE source archive must be a ZIP file")

    requested = tuple(sorted(set(int(code) for code in requested_cvm_codes)))
    if not requested:
        raise ValueError("at least one CVM code is required")
    if any(code <= 0 for code in requested):
        raise ValueError("CVM codes must be positive")

    with zipfile.ZipFile(io.BytesIO(archive_content)) as archive:
        members = tuple(sorted(archive.namelist()))
        csv_members = tuple(
            name
            for name in members
            if name.lower().endswith(".csv") and not name.endswith("/")
        )
        if not csv_members:
            raise ValueError("FRE archive contains no CSV members")

        observed_codes: set[int] = set()
        activity_fields: list[FRECandidateField] = []
        timing_fields: list[FRECandidateField] = []
        revision_fields: list[FRECandidateField] = []

        for member_name in csv_members:
            fieldnames, issuer_rows = _scan_member(
                archive.read(member_name),
                requested=requested,
            )
            for row in issuer_rows:
                code = _row_cvm_code(row, fieldnames)
                if code is not None:
                    observed_codes.add(code)

            for column_name in fieldnames:
                normalized = _normalize(column_name)
                activity_matches = tuple(
                    token for token in _ACTIVITY_TOKENS if token in normalized
                )
                timing_matches = tuple(
                    token for token in _FILING_DATE_TOKENS if token in normalized
                )
                revision_matches = tuple(
                    token for token in _REVISION_TOKENS if token in normalized
                )
                if activity_matches:
                    activity_fields.append(
                        _candidate(
                            member_name=member_name,
                            column_name=column_name,
                            matched_tokens=activity_matches,
                            issuer_rows=issuer_rows,
                        )
                    )
                if timing_matches:
                    timing_fields.append(
                        _candidate(
                            member_name=member_name,
                            column_name=column_name,
                            matched_tokens=timing_matches,
                            issuer_rows=issuer_rows,
                        )
                    )
                if revision_matches:
                    revision_fields.append(
                        _candidate(
                            member_name=member_name,
                            column_name=column_name,
                            matched_tokens=revision_matches,
                            issuer_rows=issuer_rows,
                        )
                    )

    observed = tuple(sorted(observed_codes))
    issuer_coverage_complete = set(requested).issubset(observed)
    meaningful_activity = _meaningful(activity_fields)
    meaningful_timing = _meaningful(timing_fields)
    meaningful_revision = _meaningful(revision_fields)

    blockers: set[str] = {
        FRE_ACTIVITY_TO_MODEL_MAPPING_UNPROVEN,
        HISTORICAL_MODEL_APPLICABILITY_UNPROVEN,
    }
    if not meaningful_activity:
        blockers.add(FRE_STRUCTURED_ACTIVITY_FIELD_UNAVAILABLE)
    if not meaningful_timing:
        blockers.add(FRE_FILING_TIMING_FIELDS_UNPROVEN)
    if not issuer_coverage_complete:
        blockers.add(FRE_ISSUER_COVERAGE_INCOMPLETE)

    return FREHistoricalApplicabilitySourceAudit(
        collected_at=collected_at,
        delivery_year=delivery_year,
        source_url=source_url,
        requested_cvm_codes=requested,
        archive_sha256=hashlib.sha256(archive_content).hexdigest(),
        archive_size_bytes=len(archive_content),
        member_count=len(members),
        csv_member_count=len(csv_members),
        issuer_codes_observed=observed,
        issuer_coverage_complete=issuer_coverage_complete,
        activity_candidate_fields=meaningful_activity,
        timing_candidate_fields=meaningful_timing,
        revision_candidate_fields=meaningful_revision,
        structured_activity_fields_found=bool(meaningful_activity),
        filing_timing_fields_found=bool(meaningful_timing),
        revision_metadata_fields_found=bool(meaningful_revision),
        deterministic_model_routing_supported=False,
        sector_routing_point_in_time_ready=False,
        readiness_promotion_allowed=False,
        blockers=tuple(sorted(blockers)),
    )


def _meaningful(fields: list[FRECandidateField]) -> tuple[FRECandidateField, ...]:
    return tuple(
        sorted(
            (item for item in fields if item.nonempty_value_count > 0),
            key=lambda item: (item.member_name, item.column_name),
        )
    )


def _scan_member(
    content: bytes,
    *,
    requested: tuple[int, ...],
) -> tuple[list[str], list[dict[str, str]]]:
    text = _decode(content)
    reader = csv.DictReader(io.StringIO(text), delimiter=";")
    fieldnames = [str(item).strip() for item in (reader.fieldnames or []) if item]
    if not fieldnames:
        return [], []

    cvm_column = _find_cvm_column(fieldnames)
    if cvm_column is None:
        return fieldnames, []

    requested_set = set(requested)
    issuer_rows: list[dict[str, str]] = []
    for row in reader:
        normalized_row = {
            str(key).strip(): str(value or "").strip()
            for key, value in row.items()
            if key
        }
        if _parse_cvm_code(normalized_row.get(cvm_column, "")) in requested_set:
            issuer_rows.append(normalized_row)
    return fieldnames, issuer_rows


def _decode(content: bytes) -> str:
    for encoding in ("utf-8-sig", "latin-1"):
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ValueError("FRE CSV content could not be decoded")


def _find_cvm_column(fieldnames: list[str]) -> str | None:
    by_normalized = {_normalize(name): name for name in fieldnames}
    for candidate in _CVM_CODE_COLUMNS:
        if candidate in by_normalized:
            return by_normalized[candidate]
    return None


def _row_cvm_code(row: dict[str, str], fieldnames: list[str]) -> int | None:
    column = _find_cvm_column(fieldnames)
    if column is None:
        return None
    return _parse_cvm_code(row.get(column, ""))


def _candidate(
    *,
    member_name: str,
    column_name: str,
    matched_tokens: tuple[str, ...],
    issuer_rows: list[dict[str, str]],
) -> FRECandidateField:
    values = [
        value
        for row in issuer_rows
        if (value := str(row.get(column_name, "")).strip())
    ]
    unique_values = tuple(dict.fromkeys(values))
    return FRECandidateField(
        member_name=member_name,
        column_name=column_name,
        matched_tokens=matched_tokens,
        issuer_row_count=len(issuer_rows),
        nonempty_value_count=len(values),
        sample_values=unique_values[:5],
    )


def _parse_cvm_code(value: object) -> int | None:
    text = str(value or "").strip()
    if not text:
        return None
    digits = re.sub(r"\D", "", text)
    return int(digits) if digits else None


def _normalize(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = "".join(
        char for char in normalized if not unicodedata.combining(char)
    )
    return re.sub(r"[^a-z0-9]+", "_", ascii_value.lower()).strip("_")
