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
_FILING_TIMING_TOKENS = (
    "dt_receb",
    "data_receb",
    "dt_entrega",
    "data_entrega",
    "dt_public",
    "data_public",
)
_REFERENCE_DATE_TOKENS = ("dt_refer", "data_refer", "data_referencia")
_REVISION_TOKENS = ("versao", "protocolo")
_CVM_CODE_COLUMNS = ("cd_cvm", "codigo_cvm", "cod_cvm")
_CNPJ_COLUMNS = ("cnpj_cia", "cnpj_companhia", "cnpj")
_DOCUMENT_ID_COLUMNS = ("id_doc", "id_documento")


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
    reference_candidate_fields: tuple[FRECandidateField, ...]
    revision_candidate_fields: tuple[FRECandidateField, ...]
    structured_activity_fields_found: bool
    filing_timing_fields_found: bool
    reference_metadata_fields_found: bool
    revision_metadata_fields_found: bool
    deterministic_model_routing_supported: bool
    sector_routing_point_in_time_ready: bool
    readiness_promotion_allowed: bool
    blockers: tuple[str, ...]
    effect: str = "diagnostic_only_fre_historical_applicability_source_no_routing_change"
    schema_version: str = "0.4"

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["collected_at"] = self.collected_at.isoformat()
        payload["requested_cvm_codes"] = list(self.requested_cvm_codes)
        payload["issuer_codes_observed"] = list(self.issuer_codes_observed)
        for key in (
            "activity_candidate_fields",
            "timing_candidate_fields",
            "reference_candidate_fields",
            "revision_candidate_fields",
        ):
            payload[key] = [item.to_dict() for item in getattr(self, key)]
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
    """Inspect official FRE CSV members with issuer identity propagated across detail files."""
    if delivery_year < 2010:
        raise ValueError("FRE public archives are expected from 2010 onward")
    if not source_url.startswith("https://dados.cvm.gov.br/"):
        raise ValueError("FRE source_url must use the official CVM open-data HTTPS host")
    if not archive_content.startswith(b"PK"):
        raise ValueError("FRE source archive must be a ZIP file")
    requested = tuple(sorted({int(code) for code in requested_cvm_codes}))
    if not requested or any(code <= 0 for code in requested):
        raise ValueError("positive CVM codes are required")

    with zipfile.ZipFile(io.BytesIO(archive_content)) as archive:
        members = tuple(sorted(archive.namelist()))
        csv_members = tuple(
            name
            for name in members
            if name.lower().endswith(".csv") and not name.endswith("/")
        )
        if not csv_members:
            raise ValueError("FRE archive contains no CSV members")
        parsed = {
            member_name: _parse_member(archive.read(member_name))
            for member_name in csv_members
        }

    requested_set = set(requested)
    cnpj_to_cvm, document_to_cvm = _identity_maps(
        parsed,
        requested_set=requested_set,
    )
    observed_codes: set[int] = set()
    activity_fields: list[FRECandidateField] = []
    timing_fields: list[FRECandidateField] = []
    reference_fields: list[FRECandidateField] = []
    revision_fields: list[FRECandidateField] = []

    for member_name in csv_members:
        fieldnames, rows = parsed[member_name]
        issuer_rows, member_codes = _issuer_rows(
            rows,
            fieldnames=fieldnames,
            requested_set=requested_set,
            cnpj_to_cvm=cnpj_to_cvm,
            document_to_cvm=document_to_cvm,
        )
        observed_codes.update(member_codes)
        if not issuer_rows:
            continue
        for column_name in fieldnames:
            normalized = _normalize(column_name)
            groups = (
                (activity_fields, _ACTIVITY_TOKENS),
                (timing_fields, _FILING_TIMING_TOKENS),
                (reference_fields, _REFERENCE_DATE_TOKENS),
                (revision_fields, _REVISION_TOKENS),
            )
            for target, tokens in groups:
                matches = tuple(token for token in tokens if token in normalized)
                if matches:
                    target.append(
                        _candidate(
                            member_name=member_name,
                            column_name=column_name,
                            matched_tokens=matches,
                            issuer_rows=issuer_rows,
                        )
                    )

    meaningful_activity = _meaningful(activity_fields)
    meaningful_timing = _meaningful(timing_fields)
    meaningful_reference = _meaningful(reference_fields)
    meaningful_revision = _meaningful(revision_fields)
    issuer_coverage_complete = requested_set.issubset(observed_codes)
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
        issuer_codes_observed=tuple(sorted(observed_codes)),
        issuer_coverage_complete=issuer_coverage_complete,
        activity_candidate_fields=meaningful_activity,
        timing_candidate_fields=meaningful_timing,
        reference_candidate_fields=meaningful_reference,
        revision_candidate_fields=meaningful_revision,
        structured_activity_fields_found=bool(meaningful_activity),
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


def _identity_maps(
    parsed: dict[str, tuple[list[str], list[dict[str, str]]]],
    *,
    requested_set: set[int],
) -> tuple[dict[str, int], dict[int, int]]:
    cnpj_to_cvm: dict[str, int] = {}
    document_to_cvm: dict[int, int] = {}
    for fieldnames, rows in parsed.values():
        cvm_column = _find_column(fieldnames, _CVM_CODE_COLUMNS)
        if cvm_column is None:
            continue
        cnpj_column = _find_column(fieldnames, _CNPJ_COLUMNS)
        document_column = _find_column(fieldnames, _DOCUMENT_ID_COLUMNS)
        for row in rows:
            code = _parse_int(row.get(cvm_column, ""))
            if code not in requested_set:
                continue
            if cnpj_column:
                cnpj = _digits(row.get(cnpj_column, ""))
                if cnpj:
                    cnpj_to_cvm[cnpj] = code
            if document_column:
                document_id = _parse_int(row.get(document_column, ""))
                if document_id is not None:
                    document_to_cvm[document_id] = code
    return cnpj_to_cvm, document_to_cvm


def _issuer_rows(
    rows: list[dict[str, str]],
    *,
    fieldnames: list[str],
    requested_set: set[int],
    cnpj_to_cvm: dict[str, int],
    document_to_cvm: dict[int, int],
) -> tuple[list[dict[str, str]], set[int]]:
    cvm_column = _find_column(fieldnames, _CVM_CODE_COLUMNS)
    cnpj_column = _find_column(fieldnames, _CNPJ_COLUMNS)
    document_column = _find_column(fieldnames, _DOCUMENT_ID_COLUMNS)
    selected: list[dict[str, str]] = []
    observed: set[int] = set()
    for row in rows:
        direct_code = _parse_int(row.get(cvm_column, "")) if cvm_column else None
        cnpj_code = (
            cnpj_to_cvm.get(_digits(row.get(cnpj_column, ""))) if cnpj_column else None
        )
        document_id = (
            _parse_int(row.get(document_column, "")) if document_column else None
        )
        document_code = document_to_cvm.get(document_id) if document_id is not None else None
        code = next(
            (
                candidate
                for candidate in (direct_code, cnpj_code, document_code)
                if candidate in requested_set
            ),
            None,
        )
        if code is not None:
            selected.append(row)
            observed.add(code)
    return selected, observed


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
    return FRECandidateField(
        member_name=member_name,
        column_name=column_name,
        matched_tokens=matched_tokens,
        issuer_row_count=len(issuer_rows),
        nonempty_value_count=len(values),
        sample_values=tuple(dict.fromkeys(values))[:5],
    )


def _meaningful(fields: list[FRECandidateField]) -> tuple[FRECandidateField, ...]:
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


def _parse_int(value: object) -> int | None:
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
    raise ValueError("FRE CSV content could not be decoded")


def _normalize(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = "".join(
        char for char in normalized if not unicodedata.combining(char)
    )
    return re.sub(r"[^a-z0-9]+", "_", ascii_value.lower()).strip("_")
