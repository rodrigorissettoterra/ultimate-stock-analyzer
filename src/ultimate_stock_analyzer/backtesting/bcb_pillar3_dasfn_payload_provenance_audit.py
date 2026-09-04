from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any
from urllib.parse import urlparse

from ultimate_stock_analyzer.backtesting.bcb_pillar3_dasfn_pit_source_audit import (
    BANK_EVIDENCE_NOT_POINT_IN_TIME,
    PILLAR3_DASFN_HISTORICAL_VINTAGE_QUERY_UNPROVEN,
    PILLAR3_DASFN_PAYLOAD_PUBLICATION_TIMESTAMP_UNPROVEN,
    PILLAR3_DASFN_REVISION_HISTORY_UNPROVEN,
)
PILLAR3_DASFN_PAYLOAD_SAMPLE_MISSING = "PILLAR3_DASFN_PAYLOAD_SAMPLE_MISSING"
PILLAR3_DASFN_PAYLOAD_UNAVAILABLE = "PILLAR3_DASFN_PAYLOAD_UNAVAILABLE"
PILLAR3_DASFN_PAYLOAD_FINAL_URL_UNTRUSTED = (
    "PILLAR3_DASFN_PAYLOAD_FINAL_URL_UNTRUSTED"
)
PILLAR3_DASFN_PAYLOAD_BODY_INCOMPLETE = "PILLAR3_DASFN_PAYLOAD_BODY_INCOMPLETE"
PILLAR3_DASFN_PAYLOAD_JSON_UNUSABLE = "PILLAR3_DASFN_PAYLOAD_JSON_UNUSABLE"

_REVISION_TOKENS = (
    "asof",
    "atualiz",
    "publica",
    "revision",
    "revisao",
    "updated",
    "version",
    "versao",
    "vintage",
)


@dataclass(frozen=True, slots=True)
class Pillar3PayloadSampleKey:
    cnpj_instituicao: str
    reference_year: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class Pillar3InstitutionPayloadProbeInput:
    cnpj_instituicao: str
    reference_year: int
    version: str
    resource: str
    central_url_dados: str
    requested_url: str
    final_url: str | None
    status_code: int | None
    content_type: str | None
    response_headers: tuple[tuple[str, str], ...]
    content: bytes | None
    body_complete: bool
    transport_error: str | None = None


@dataclass(frozen=True, slots=True)
class Pillar3InstitutionPayloadEvidence:
    cnpj_instituicao: str
    reference_year: int
    version: str
    resource: str
    central_url_dados: str
    requested_url: str
    final_url: str | None
    status_code: int | None
    content_type: str | None
    response_headers: tuple[tuple[str, str], ...]
    sha256: str | None
    size_bytes: int
    body_complete: bool
    transport_error: str | None
    trusted_http_success: bool
    json_usable: bool
    observed_json_fields: tuple[str, ...]
    revision_like_json_fields: tuple[str, ...]
    last_modified: str | None
    etag: str | None
    response_date: str | None
    historical_reference_payload_reachable_now: bool

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["response_headers"] = [list(item) for item in self.response_headers]
        payload["observed_json_fields"] = list(self.observed_json_fields)
        payload["revision_like_json_fields"] = list(self.revision_like_json_fields)
        return payload


@dataclass(frozen=True, slots=True)
class BCBPillar3InstitutionPayloadProvenanceAudit:
    collected_at: datetime
    expected_samples: tuple[Pillar3PayloadSampleKey, ...]
    payloads: tuple[Pillar3InstitutionPayloadEvidence, ...]
    sampled_institutions: tuple[str, ...]
    reachable_payload_count: int
    json_usable_payload_count: int
    historical_reference_reachable_count: int
    last_modified_observed_count: int
    etag_observed_count: int
    payload_publication_timestamp_proven: bool
    revision_history_proven: bool
    historical_vintage_query_proven: bool
    historical_replay_ready: bool
    bank_evidence_point_in_time_ready: bool
    readiness_promotion_allowed: bool
    blockers: tuple[str, ...]
    effect: str = "diagnostic_only_pillar3_payload_provenance_no_readiness_change"
    schema_version: str = "0.1"

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "effect": self.effect,
            "collected_at": self.collected_at.isoformat(),
            "expected_samples": [item.to_dict() for item in self.expected_samples],
            "payloads": [item.to_dict() for item in self.payloads],
            "sampled_institutions": list(self.sampled_institutions),
            "reachable_payload_count": self.reachable_payload_count,
            "json_usable_payload_count": self.json_usable_payload_count,
            "historical_reference_reachable_count": self.historical_reference_reachable_count,
            "last_modified_observed_count": self.last_modified_observed_count,
            "etag_observed_count": self.etag_observed_count,
            "payload_publication_timestamp_proven": self.payload_publication_timestamp_proven,
            "revision_history_proven": self.revision_history_proven,
            "historical_vintage_query_proven": self.historical_vintage_query_proven,
            "historical_replay_ready": self.historical_replay_ready,
            "bank_evidence_point_in_time_ready": self.bank_evidence_point_in_time_ready,
            "readiness_promotion_allowed": self.readiness_promotion_allowed,
            "blockers": list(self.blockers),
        }


def audit_bcb_pillar3_institution_payload_provenance(
    *,
    expected_samples: tuple[Pillar3PayloadSampleKey, ...] | list[Pillar3PayloadSampleKey],
    probes: tuple[Pillar3InstitutionPayloadProbeInput, ...]
    | list[Pillar3InstitutionPayloadProbeInput],
    collected_at: datetime,
) -> BCBPillar3InstitutionPayloadProvenanceAudit:
    if collected_at.tzinfo is None or collected_at.utcoffset() is None:
        raise ValueError("collected_at must be timezone-aware")

    expected = tuple(expected_samples)
    if not expected:
        raise ValueError("expected_samples must not be empty")
    _validate_sample_keys(expected)
    normalized = tuple(probes)
    _validate_probe_keys(normalized, expected)

    evidence = tuple(_payload_evidence(item, collected_at=collected_at) for item in normalized)
    evidence_by_key = {
        (item.cnpj_instituicao, item.reference_year): item for item in evidence
    }
    expected_keys = {(item.cnpj_instituicao, item.reference_year) for item in expected}
    observed_keys = set(evidence_by_key)

    blockers = {
        BANK_EVIDENCE_NOT_POINT_IN_TIME,
        PILLAR3_DASFN_PAYLOAD_PUBLICATION_TIMESTAMP_UNPROVEN,
        PILLAR3_DASFN_REVISION_HISTORY_UNPROVEN,
        PILLAR3_DASFN_HISTORICAL_VINTAGE_QUERY_UNPROVEN,
    }
    if observed_keys != expected_keys:
        blockers.add(PILLAR3_DASFN_PAYLOAD_SAMPLE_MISSING)
    if any(not item.trusted_http_success for item in evidence):
        blockers.add(PILLAR3_DASFN_PAYLOAD_UNAVAILABLE)
    if any(
        item.status_code is not None
        and 200 <= item.status_code < 300
        and not _same_https_host(item.central_url_dados, item.final_url)
        for item in evidence
    ):
        blockers.add(PILLAR3_DASFN_PAYLOAD_FINAL_URL_UNTRUSTED)
    if any(not item.body_complete for item in evidence):
        blockers.add(PILLAR3_DASFN_PAYLOAD_BODY_INCOMPLETE)
    if any(item.trusted_http_success and not item.json_usable for item in evidence):
        blockers.add(PILLAR3_DASFN_PAYLOAD_JSON_UNUSABLE)

    reachable = sum(item.trusted_http_success for item in evidence)
    json_usable = sum(item.json_usable for item in evidence)
    historical_reachable = sum(item.historical_reference_payload_reachable_now for item in evidence)
    last_modified = sum(item.last_modified is not None for item in evidence)
    etag = sum(item.etag is not None for item in evidence)

    return BCBPillar3InstitutionPayloadProvenanceAudit(
        collected_at=collected_at,
        expected_samples=expected,
        payloads=evidence,
        sampled_institutions=tuple(sorted({item.cnpj_instituicao for item in evidence})),
        reachable_payload_count=reachable,
        json_usable_payload_count=json_usable,
        historical_reference_reachable_count=historical_reachable,
        last_modified_observed_count=last_modified,
        etag_observed_count=etag,
        payload_publication_timestamp_proven=False,
        revision_history_proven=False,
        historical_vintage_query_proven=False,
        historical_replay_ready=False,
        bank_evidence_point_in_time_ready=False,
        readiness_promotion_allowed=False,
        blockers=tuple(sorted(blockers)),
    )


def _validate_sample_keys(keys: tuple[Pillar3PayloadSampleKey, ...]) -> None:
    seen: set[tuple[str, int]] = set()
    for item in keys:
        _validate_cnpj(item.cnpj_instituicao)
        if item.reference_year < 2000:
            raise ValueError("reference_year must be >= 2000")
        key = (item.cnpj_instituicao, item.reference_year)
        if key in seen:
            raise ValueError("expected_samples contains duplicate institution-year")
        seen.add(key)


def _validate_probe_keys(
    probes: tuple[Pillar3InstitutionPayloadProbeInput, ...],
    expected: tuple[Pillar3PayloadSampleKey, ...],
) -> None:
    expected_keys = {(item.cnpj_instituicao, item.reference_year) for item in expected}
    seen: set[tuple[str, int]] = set()
    for probe in probes:
        _validate_cnpj(probe.cnpj_instituicao)
        key = (probe.cnpj_instituicao, probe.reference_year)
        if key not in expected_keys:
            raise ValueError("payload probe is outside expected_samples")
        if key in seen:
            raise ValueError("payload probes contain duplicate institution-year")
        seen.add(key)
        if probe.requested_url != probe.central_url_dados:
            raise ValueError("requested_url must equal the central URLDados value")
        parsed = urlparse(probe.central_url_dados)
        if parsed.scheme != "https" or not parsed.hostname:
            raise ValueError("central URLDados must be an absolute HTTPS URL")


def _validate_cnpj(value: str) -> None:
    if len(value) != 14 or not value.isdigit():
        raise ValueError("CNPJ must contain exactly 14 digits")


def _payload_evidence(
    probe: Pillar3InstitutionPayloadProbeInput,
    *,
    collected_at: datetime,
) -> Pillar3InstitutionPayloadEvidence:
    headers = tuple(sorted((key.casefold(), value) for key, value in probe.response_headers))
    header_map = dict(headers)
    if probe.status_code is None:
        if probe.transport_error is None:
            raise ValueError("probe without HTTP status must preserve transport_error")
        if probe.content is not None:
            raise ValueError("transport-error probe must not contain response content")
        if not probe.body_complete:
            raise ValueError("transport-error probe cannot declare incomplete HTTP body")
        sha256 = None
        size_bytes = 0
        json_usable = False
        fields: tuple[str, ...] = ()
        revision_like: tuple[str, ...] = ()
        trusted = False
    else:
        if not 100 <= probe.status_code <= 599:
            raise ValueError("HTTP status must be between 100 and 599")
        if probe.transport_error is not None:
            raise ValueError("HTTP response probe must not contain transport_error")
        content = probe.content or b""
        sha256 = hashlib.sha256(content).hexdigest()
        size_bytes = len(content)
        trusted = bool(
            200 <= probe.status_code < 300
            and probe.body_complete
            and _same_https_host(probe.central_url_dados, probe.final_url)
        )
        parsed = _try_json(content) if trusted else None
        json_usable = parsed is not None
        fields = _collect_json_fields(parsed) if parsed is not None else ()
        revision_like = tuple(field for field in fields if _looks_revision_like(field))

    historical_reference = bool(
        probe.reference_year < collected_at.year and trusted and json_usable
    )
    return Pillar3InstitutionPayloadEvidence(
        cnpj_instituicao=probe.cnpj_instituicao,
        reference_year=probe.reference_year,
        version=probe.version,
        resource=probe.resource,
        central_url_dados=probe.central_url_dados,
        requested_url=probe.requested_url,
        final_url=probe.final_url,
        status_code=probe.status_code,
        content_type=probe.content_type,
        response_headers=headers,
        sha256=sha256,
        size_bytes=size_bytes,
        body_complete=probe.body_complete,
        transport_error=probe.transport_error,
        trusted_http_success=trusted,
        json_usable=json_usable,
        observed_json_fields=fields,
        revision_like_json_fields=revision_like,
        last_modified=header_map.get("last-modified"),
        etag=header_map.get("etag"),
        response_date=header_map.get("date"),
        historical_reference_payload_reachable_now=historical_reference,
    )


def _same_https_host(expected_url: str, final_url: str | None) -> bool:
    if final_url is None:
        return False
    expected = urlparse(expected_url)
    final = urlparse(final_url)
    return bool(
        expected.scheme == "https"
        and final.scheme == "https"
        and expected.hostname
        and final.hostname
        and expected.hostname.casefold() == final.hostname.casefold()
    )


def _try_json(content: bytes) -> Any | None:
    if not content:
        return None
    try:
        return json.loads(content)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None


def _collect_json_fields(payload: Any) -> tuple[str, ...]:
    fields: set[str] = set()
    stack: list[tuple[Any, int]] = [(payload, 0)]
    visited = 0
    while stack and visited < 10000:
        value, depth = stack.pop()
        visited += 1
        if depth > 4:
            continue
        if isinstance(value, dict):
            for key, child in value.items():
                fields.add(str(key))
                stack.append((child, depth + 1))
        elif isinstance(value, list):
            for child in value[:1000]:
                stack.append((child, depth + 1))
    return tuple(sorted(fields))


def _looks_revision_like(name: str) -> bool:
    normalized = name.casefold().replace("_", "").replace("-", "").replace(" ", "")
    return any(token in normalized for token in _REVISION_TOKENS)
