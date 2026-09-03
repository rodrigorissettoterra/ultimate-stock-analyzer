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

FCA_APPLICABILITY_FIELD_UNAVAILABLE = "FCA_APPLICABILITY_FIELD_UNAVAILABLE"
FCA_ISSUER_COVERAGE_INCOMPLETE = "FCA_ISSUER_COVERAGE_INCOMPLETE"
FCA_FILING_TIMING_FIELDS_UNPROVEN = "FCA_FILING_TIMING_FIELDS_UNPROVEN"
FCA_APPLICABILITY_TO_MODEL_MAPPING_UNPROVEN = "FCA_APPLICABILITY_TO_MODEL_MAPPING_UNPROVEN"
HISTORICAL_MODEL_APPLICABILITY_UNPROVEN = "HISTORICAL_MODEL_APPLICABILITY_UNPROVEN"

_APPLICABILITY_TOKENS = (
    "atividade",
    "setor",
    "cnae",
    "ramo",
    "segmento",
    "objeto_social",
    "objeto",
    "classificacao",
    "categoria",
    "tipo_emissor",
    "natureza",
)
_FILING_TIMING_TOKENS = (
    "dt_receb",
    "data_receb",
    "dt_entrega",
    "data_entrega",
    "dt_public",
    "data_public",
)
_REFERENCE_DATE_TOKENS = (
    "dt_refer",
    "data_refer",
    "data_referencia",
)
_REVISION_TOKENS = (
    "versao",
    "protocolo",
)
_CVM_CODE_COLUMNS = ("cd_cvm", "codigo_cvm", "cod_cvm")
_CNPJ_COLUMNS = ("cnpj_companhia", "cnpj_cia", "cnpj")


@dataclass(frozen=True, slots=True)
class FCAMemberSchema:
    member_name: str
    columns: tuple[str, ...]
    issuer_row_count: int

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["columns"] = list(self.columns)
        return payload


@dataclass(frozen=True, slots=True)
class FCACandidateField:
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
class FCAHistoricalApplicabilitySourceAudit:
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
    member_schemas: tuple[FCAMemberSchema, ...]
    applicability_candidate_fields: tuple[FCACandidateField, ...]
    timing_candidate_fields: tuple[FCACandidateField, ...]
    reference_candidate_fields: tuple[FCACandidateField, ...]
    revision_candidate_fields: tuple[FCACandidateField, ...]
    applicability_fields_found: bool
    filing_timing_fields_found: bool
    reference_metadata_fields_found: bool
    revision_metadata_fields_found: bool
    deterministic_model_routing_supported: bool
    sector_routing_point_in_time_ready: bool
    readiness_promotion_allowed: bool
    blockers: tuple[str, ...]
    effect: str = "diagnostic_only_fca_historical_applicability_source_no_routing_change"
    schema_version: str = "0.1"

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["collected_at"] = self.collected_at.isoformat()
        payload["requested_cvm_codes"] = list(self.requested_cvm_codes)
        payload["issuer_codes_observed"] = list(self.issuer_codes_observed)
        payload["member_schemas"] = [item.to_dict() for item in self.member_schemas]
        payload["applicability_candidate_fields"] = [
            item.to_dict() for item in self.applicability_candidate_fields
        ]
        payload["timing_candidate_fields"] = [
            item.to_dict() for item in self.timing_candidate_fields
        ]
        payload["reference_candidate_fields"] = [
            item.to_dict() for item in self.reference_candidate_fields
        ]
        payload["revision_candidate_fields"] = [
            item.to_dict() for item in self.revision_candidate_fields
        ]
        payload["blockers"] = list(self.blockers)
        return payload


def audit_fca_historical_applicability_source(
    *,
    archive_content: bytes,
    collected_at: datetime,
    delivery_year: int,
    source_url: str,
    requested_cvm_codes: tuple[int, ...] | list[int],
) -> FCAHistoricalApplicabilitySourceAudit:
    """Inspect one official FCA archive for evidence usable in historical model routing.

    Discovery is deliberately fail-closed. Candidate fields are surfaced with bounded values, but
    no field is mapped to a project model family and no readiness status is promoted here.
    """
    if delivery_year < 2010:
        raise ValueError("FCA public archives are expected from 2010 onward")
    if not source_url.startswith("https://dados.cvm.gov.br/"):
        raise ValueError("FCA source_url must use the official CVM open-data HTTPS host")
    if not archive_content.startswith(b"PK"):
        raise ValueError("FCA source archive must be a ZIP file")

    requested = tuple(sorted({int(code) for code in requested_cvm_codes}))
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
            raise ValueError("FCA archive contains no CSV members")
        parsed = {
            member_name: _parse_member(archive.read(member_name))
            for member_name in csv_members
        }

    requested_set = set(requested)
    cnpj_to_cvm = _requested_cnpj_map(parsed, requested_set=requested_set)
    observed_codes: set[int] = set()
    schemas: list[FCAMemberSchema] = []
    applicability_fields: list[FCACandidateField] = []
    timing_fields: list[FCACandidateField] = []
    reference_fields: list[FCACandidateField] = []
    revision_fields: list[FCACandidateField] = []

    for member_name in csv_members:
        fieldnames, rows = parsed[member_name]
        issuer_rows, member_codes = _issuer_rows(
            rows,
            fieldnames=fieldnames,
            requested_set=requested_set,
            cnpj_to_cvm=cnpj_to_cvm,
        )
        observed_codes.update(member_codes)
        schemas.append(
            FCAMemberSchema(
                member_name=member_name,
                columns=tuple(fieldnames),
                issuer_row_count=len(issuer_rows),
            )
        )
        if not issuer_rows:
            continue
        for column_name in fieldnames:
            normalized = _normalize(column_name)
            applicability_matches = tuple(
                token for token in _APPLICABILITY_TOKENS if token in normalized
            )
            timing_matches = tuple(
                token for token in _FILING_TIMING_TOKENS if token in normalized
            )
            reference_matches = tuple(
                token for token in _REFERENCE_DATE_TOKENS if token in normalized
            )
            revision_matches = tuple(
                token for token in _REVISION_TOKENS if token in normalized
            )
            if applicability_matches:
                applicability_fields.append(
                    _candidate(
                        member_name=member_name,
                        column_name=column_name,
                        matched_tokens=applicability_matches,
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
            if reference_matches:
                reference_fields.append(
                    _candidate(
                        member_name=member_name,
                        column_name=column_name,
                        matched_tokens=reference_matches,
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

    meaningful_applicability = _meaningful(applicability_fields)
    meaningful_timing = _meaningful(timing_fields)
    meaningful_reference = _meaningful(reference_fields)
    meaningful_revision = _meaningful(revision_fields)
    observed = tuple(sorted(observed_codes))
    issuer_coverage_complete = requested_set.issubset(observed_codes)

    blockers: set[str] = {
        FCA_APPLICABILITY_TO_MODEL_MAPPING_UNPROVEN,
        HISTORICAL_MODEL_APPLICABILITY_UNPROVEN,
    }
    if not meaningful_applicability:
        blockers.add(FCA_APPLICABILITY_FIELD_UNAVAILABLE)
    if not meaningful_timing:
        blockers.add(FCA_FILING_TIMING_FIELDS_UNPROVEN)
    if not issuer_coverage_complete:
        blockers.add(FCA_ISSUER_COVERAGE_INCOMPLETE)

    return FCAHistoricalApplicabilitySourceAudit(
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
        member_schemas=tuple(sorted(schemas, key=lambda item: item.member_name)),
        applicability_candidate_fields=meaningful_applicability,
        timing_candidate_fields=meaningful_timing,
        reference_candidate_fields=meaningful_reference,
        revision_candidate_fields=meaningful_revision,
        applicability_fields_found=bool(meaningful_applicability),
        filing_timing_fields_found=bool(meaningful_timing),
        reference_metadata_fields_found=bool(meaningful_reference),
        revision_metadata_fields_found=bool(meaningful_revision),
        deterministic_model_routing_supported=False,
        sector_routing_point_in_time_ready=False,
        readiness_promotion_allowed=False,
        blockers=tuple(sorted(blockers)),
    )


def _parse_member(content: bytes) -> tuple[list[str], list[dict[str, str]]]:
    text = _decode(content)
    reader = csv.DictReader(io.StringIO(text), delimiter=";")
    fieldnames = [str(item).strip() for item in (reader.fieldnames or []) if item]
    rows = [
        {
            str(key).strip(): str(value or "").strip()
            for key, value in row.items()
            if key
        }
        for row in reader
    ]
    return fieldnames, rows


def _requested_cnpj_map(
    parsed: dict[str, tuple[list[str], list[dict[str, str]]]],
    *,
    requested_set: set[int],
) -> dict[str, int]:
    output: dict[str, int] = {}
    for fieldnames, rows in parsed.values():
        cvm_column = _find_column(fieldnames, _CVM_CODE_COLUMNS)
        cnpj_column = _find_column(fieldnames, _CNPJ_COLUMNS)
        if cvm_column is None or cnpj_column is None:
            continue
        for row in rows:
            code = _parse_cvm_code(row.get(cvm_column, ""))
            cnpj = _digits(row.get(cnpj_column, ""))
            if code in requested_set and cnpj:
                output[cnpj] = code
    return output


def _issuer_rows(
    rows: list[dict[str, str]],
    *,
    fieldnames: list[str],
    requested_set: set[int],
    cnpj_to_cvm: dict[str, int],
) -> tuple[list[dict[str, str]], set[int]]:
    cvm_column = _find_column(fieldnames, _CVM_CODE_COLUMNS)
    cnpj_column = _find_column(fieldnames, _CNPJ_COLUMNS)
    selected: list[dict[str, str]] = []
    observed: set[int] = set()
    for row in rows:
        direct_code = _parse_cvm_code(row.get(cvm_column, "")) if cvm_column else None
        cnpj_code = None
        if cnpj_column:
            cnpj_code = cnpj_to_cvm.get(_digits(row.get(cnpj_column, "")))
        code = direct_code if direct_code in requested_set else cnpj_code
        if code in requested_set:
            selected.append(row)
            observed.add(code)
    return selected, observed


def _candidate(
    *,
    member_name: str,
    column_name: str,
    matched_tokens: tuple[str, ...],
    issuer_rows: list[dict[str, str]],
) -> FCACandidateField:
    values = [
        value
        for row in issuer_rows
        if (value := str(row.get(column_name, "")).strip())
    ]
    unique_values = tuple(dict.fromkeys(values))
    return FCACandidateField(
        member_name=member_name,
        column_name=column_name,
        matched_tokens=matched_tokens,
        issuer_row_count=len(issuer_rows),
        nonempty_value_count=len(values),
        sample_values=unique_values[:8],
    )


def _meaningful(fields: list[FCACandidateField]) -> tuple[FCACandidateField, ...]:
    return tuple(
        sorted(
            (item for item in fields if item.nonempty_value_count > 0),
            key=lambda item: (item.member_name, item.column_name),
        )
    )


def _find_column(fieldnames: list[str], candidates: tuple[str, ...]) -> str | None:
    by_normalized = {_normalize(name): name for name in fieldnames}
    for candidate in candidates:
        if candidate in by_normalized:
            return by_normalized[candidate]
    return None


def _parse_cvm_code(value: object) -> int | None:
    digits = _digits(value)
    return int(digits) if digits else None


def _digits(value: object) -> str:
    return re.sub(r"\D", "", str(value or "").strip())


def _decode(content: bytes) -> str:
    for encoding in ("utf-8-sig", "latin-1"):
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ValueError("FCA CSV content could not be decoded")


def _normalize(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = "".join(
        char for char in normalized if not unicodedata.combining(char)
    )
    return re.sub(r"[^a-z0-9]+", "_", ascii_value.lower()).strip("_")
