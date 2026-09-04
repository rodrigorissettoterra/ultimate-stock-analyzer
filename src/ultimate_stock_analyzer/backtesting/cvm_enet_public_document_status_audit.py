from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from datetime import date, datetime
from typing import Any
from urllib.parse import urlparse

from ultimate_stock_analyzer.backtesting.cvm_ipe_pillar3_filing_ledger import (
    BANK_EVIDENCE_NOT_POINT_IN_TIME,
    PILLAR3_IPE_REVISION_HISTORY_COMPLETENESS_UNPROVEN,
)

PILLAR3_IPE_DOCUMENT_ACTION_HISTORY_UNPROVEN = (
    "PILLAR3_IPE_DOCUMENT_ACTION_HISTORY_UNPROVEN"
)
PILLAR3_IPE_ENET_PUBLIC_QUERY_UNAVAILABLE = "PILLAR3_IPE_ENET_PUBLIC_QUERY_UNAVAILABLE"
PILLAR3_IPE_ENET_PUBLIC_CONTRACT_UNUSABLE = (
    "PILLAR3_IPE_ENET_PUBLIC_CONTRACT_UNUSABLE"
)
PILLAR3_IPE_ENET_TARGET_DOCUMENT_NOT_OBSERVED = (
    "PILLAR3_IPE_ENET_TARGET_DOCUMENT_NOT_OBSERVED"
)
PILLAR3_IPE_ENET_FINAL_URL_UNTRUSTED = "PILLAR3_IPE_ENET_FINAL_URL_UNTRUSTED"
PILLAR3_IPE_ENET_RESPONSE_TOO_LARGE = "PILLAR3_IPE_ENET_RESPONSE_TOO_LARGE"

ENET_PUBLIC_PAGE_URL = "https://www.rad.cvm.gov.br/ENETWeb/frmConsultaExternaCVM.aspx"
ENET_PUBLIC_LIST_URL = f"{ENET_PUBLIC_PAGE_URL}/ListarDocumentos"
_ALLOWED_HOSTS = {"www.rad.cvm.gov.br", "rad.cvm.gov.br"}
_STATUS_TOKENS = ("ATIVO", "LIBERADO", "CANCELADO", "BLOQUEADO")
_MODALITY_TOKENS = (
    "APRESENTACAO",
    "REAPRESENTACAO ESPONTANEA",
    "REAPRESENTACAO",
)
_VERSION_PATTERNS = (
    re.compile(r"(?:^|[^A-Z0-9])V(?:ERSAO)?\s*[:=-]?\s*(\d{1,3})(?:[^A-Z0-9]|$)"),
    re.compile(r"(?:^|[^A-Z0-9])VERSAO\s+(\d{1,3})(?:[^A-Z0-9]|$)"),
)


@dataclass(frozen=True, slots=True)
class ENETPublicQueryProbeInput:
    delivery_date: date
    requested_url: str
    final_url: str | None
    status_code: int | None
    content_type: str | None
    content: bytes | None
    body_complete: bool = True
    transport_error: str | None = None


@dataclass(frozen=True, slots=True)
class ENETPublicQueryEvidence:
    delivery_date: date
    requested_url: str
    final_url: str | None
    status_code: int | None
    content_type: str | None
    sha256: str | None
    size_bytes: int
    body_complete: bool
    transport_error: str | None
    trusted_http_success: bool
    webmethod_contract_usable: bool
    server_reported_error: bool | None
    server_session_expired: bool | None
    flattened_payload_sha256: str | None
    flattened_payload_size: int
    target_cvm_code_observed: bool
    pillar3_observed: bool
    observed_status_tokens: tuple[str, ...]
    observed_version_tokens: tuple[int, ...]
    observed_modality_tokens: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["delivery_date"] = self.delivery_date.isoformat()
        payload["observed_status_tokens"] = list(self.observed_status_tokens)
        payload["observed_version_tokens"] = list(self.observed_version_tokens)
        payload["observed_modality_tokens"] = list(self.observed_modality_tokens)
        return payload


@dataclass(frozen=True, slots=True)
class CVMENETPublicDocumentStatusAudit:
    cvm_code: int
    generated_at: datetime
    query_evidence: tuple[ENETPublicQueryEvidence, ...]
    query_count: int
    trusted_query_count: int
    usable_contract_count: int
    target_document_query_count: int
    observed_status_tokens: tuple[str, ...]
    observed_version_tokens: tuple[int, ...]
    observed_modality_tokens: tuple[str, ...]
    public_current_status_contract_observed: bool
    historical_action_timeline_proven: bool
    revision_history_completeness_proven: bool
    bank_evidence_point_in_time_ready: bool
    readiness_promotion_allowed: bool
    blockers: tuple[str, ...]
    effect: str = "diagnostic_only_cvm_enet_public_status_no_readiness_change"
    schema_version: str = "0.1"

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "effect": self.effect,
            "cvm_code": self.cvm_code,
            "generated_at": self.generated_at.isoformat(),
            "query_evidence": [item.to_dict() for item in self.query_evidence],
            "query_count": self.query_count,
            "trusted_query_count": self.trusted_query_count,
            "usable_contract_count": self.usable_contract_count,
            "target_document_query_count": self.target_document_query_count,
            "observed_status_tokens": list(self.observed_status_tokens),
            "observed_version_tokens": list(self.observed_version_tokens),
            "observed_modality_tokens": list(self.observed_modality_tokens),
            "public_current_status_contract_observed": self.public_current_status_contract_observed,
            "historical_action_timeline_proven": self.historical_action_timeline_proven,
            "revision_history_completeness_proven": self.revision_history_completeness_proven,
            "bank_evidence_point_in_time_ready": self.bank_evidence_point_in_time_ready,
            "readiness_promotion_allowed": self.readiness_promotion_allowed,
            "blockers": list(self.blockers),
        }


def audit_cvm_enet_public_document_status(
    *,
    cvm_code: int,
    probes: tuple[ENETPublicQueryProbeInput, ...] | list[ENETPublicQueryProbeInput],
    generated_at: datetime,
) -> CVMENETPublicDocumentStatusAudit:
    if cvm_code <= 0:
        raise ValueError("cvm_code must be positive")
    if generated_at.tzinfo is None or generated_at.utcoffset() is None:
        raise ValueError("generated_at must be timezone-aware")
    normalized = tuple(probes)
    if not normalized:
        raise ValueError("probes must not be empty")
    if len({item.delivery_date for item in normalized}) != len(normalized):
        raise ValueError("probes must contain at most one query per delivery date")

    evidence = tuple(_query_evidence(item, cvm_code=cvm_code) for item in normalized)
    blockers = {
        BANK_EVIDENCE_NOT_POINT_IN_TIME,
        PILLAR3_IPE_REVISION_HISTORY_COMPLETENESS_UNPROVEN,
        PILLAR3_IPE_DOCUMENT_ACTION_HISTORY_UNPROVEN,
    }
    if any(not item.trusted_http_success for item in evidence):
        blockers.add(PILLAR3_IPE_ENET_PUBLIC_QUERY_UNAVAILABLE)
    if any(not item.webmethod_contract_usable for item in evidence):
        blockers.add(PILLAR3_IPE_ENET_PUBLIC_CONTRACT_UNUSABLE)
    if any(
        item.status_code is not None
        and 200 <= item.status_code < 300
        and not _trusted_final_url(item.final_url)
        for item in evidence
    ):
        blockers.add(PILLAR3_IPE_ENET_FINAL_URL_UNTRUSTED)
    if any(not item.body_complete for item in evidence):
        blockers.add(PILLAR3_IPE_ENET_RESPONSE_TOO_LARGE)
    if any(
        item.webmethod_contract_usable
        and not (item.target_cvm_code_observed and item.pillar3_observed)
        for item in evidence
    ):
        blockers.add(PILLAR3_IPE_ENET_TARGET_DOCUMENT_NOT_OBSERVED)

    statuses = tuple(sorted({token for item in evidence for token in item.observed_status_tokens}))
    versions = tuple(sorted({token for item in evidence for token in item.observed_version_tokens}))
    modalities = tuple(
        sorted({token for item in evidence for token in item.observed_modality_tokens})
    )
    current_status_contract = bool(
        evidence
        and all(item.webmethod_contract_usable for item in evidence)
        and all(item.target_cvm_code_observed and item.pillar3_observed for item in evidence)
        and statuses
    )
    return CVMENETPublicDocumentStatusAudit(
        cvm_code=cvm_code,
        generated_at=generated_at,
        query_evidence=evidence,
        query_count=len(evidence),
        trusted_query_count=sum(item.trusted_http_success for item in evidence),
        usable_contract_count=sum(item.webmethod_contract_usable for item in evidence),
        target_document_query_count=sum(
            item.target_cvm_code_observed and item.pillar3_observed for item in evidence
        ),
        observed_status_tokens=statuses,
        observed_version_tokens=versions,
        observed_modality_tokens=modalities,
        public_current_status_contract_observed=current_status_contract,
        historical_action_timeline_proven=False,
        revision_history_completeness_proven=False,
        bank_evidence_point_in_time_ready=False,
        readiness_promotion_allowed=False,
        blockers=tuple(sorted(blockers)),
    )


def _query_evidence(
    probe: ENETPublicQueryProbeInput,
    *,
    cvm_code: int,
) -> ENETPublicQueryEvidence:
    if probe.requested_url != ENET_PUBLIC_LIST_URL:
        raise ValueError("requested_url must be the fixed public ENET ListarDocumentos endpoint")
    if probe.status_code is None:
        if probe.transport_error is None:
            raise ValueError("probe without HTTP status must preserve transport_error")
        if probe.content is not None:
            raise ValueError("transport-error probe must not contain response content")
        return _empty_evidence(probe)
    if not 100 <= probe.status_code <= 599:
        raise ValueError("HTTP status must be between 100 and 599")
    if probe.transport_error is not None:
        raise ValueError("HTTP response probe must not contain transport_error")

    content = probe.content or b""
    trusted = bool(
        200 <= probe.status_code < 300
        and probe.body_complete
        and _trusted_final_url(probe.final_url)
    )
    envelope = _try_webmethod_envelope(content) if trusted else None
    contract_usable = envelope is not None
    server_error: bool | None = None
    session_expired: bool | None = None
    flattened: str | None = None
    if envelope is not None:
        server_error = envelope["temErro"]
        session_expired = envelope["expirouSessao"]
        flattened = envelope["dados"]
        contract_usable = not server_error and not session_expired and isinstance(flattened, str)
    flattened_for_analysis = flattened if contract_usable and flattened is not None else ""
    normalized_text = _normalize(flattened_for_analysis)
    statuses = tuple(token for token in _STATUS_TOKENS if token in normalized_text)
    modalities = tuple(token for token in _MODALITY_TOKENS if token in normalized_text)
    versions = _version_tokens(normalized_text)
    return ENETPublicQueryEvidence(
        delivery_date=probe.delivery_date,
        requested_url=probe.requested_url,
        final_url=probe.final_url,
        status_code=probe.status_code,
        content_type=probe.content_type,
        sha256=hashlib.sha256(content).hexdigest(),
        size_bytes=len(content),
        body_complete=probe.body_complete,
        transport_error=None,
        trusted_http_success=trusted,
        webmethod_contract_usable=contract_usable,
        server_reported_error=server_error,
        server_session_expired=session_expired,
        flattened_payload_sha256=(
            hashlib.sha256(flattened_for_analysis.encode("utf-8")).hexdigest()
            if flattened_for_analysis
            else None
        ),
        flattened_payload_size=len(flattened_for_analysis.encode("utf-8")),
        target_cvm_code_observed=str(cvm_code) in flattened_for_analysis,
        pillar3_observed="PILAR 3" in normalized_text or "PILAR III" in normalized_text,
        observed_status_tokens=statuses,
        observed_version_tokens=versions,
        observed_modality_tokens=modalities,
    )


def _empty_evidence(probe: ENETPublicQueryProbeInput) -> ENETPublicQueryEvidence:
    return ENETPublicQueryEvidence(
        delivery_date=probe.delivery_date,
        requested_url=probe.requested_url,
        final_url=probe.final_url,
        status_code=None,
        content_type=probe.content_type,
        sha256=None,
        size_bytes=0,
        body_complete=probe.body_complete,
        transport_error=probe.transport_error,
        trusted_http_success=False,
        webmethod_contract_usable=False,
        server_reported_error=None,
        server_session_expired=None,
        flattened_payload_sha256=None,
        flattened_payload_size=0,
        target_cvm_code_observed=False,
        pillar3_observed=False,
        observed_status_tokens=(),
        observed_version_tokens=(),
        observed_modality_tokens=(),
    )


def _try_webmethod_envelope(content: bytes) -> dict[str, Any] | None:
    if not content:
        return None
    try:
        payload = json.loads(content)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict) or set(payload) != {"d"}:
        return None
    inner = payload["d"]
    if not isinstance(inner, dict):
        return None
    required = {"temErro", "expirouSessao", "msgErro", "dados"}
    if not required.issubset(inner):
        return None
    if not isinstance(inner["temErro"], bool) or not isinstance(inner["expirouSessao"], bool):
        return None
    if inner["msgErro"] is not None and not isinstance(inner["msgErro"], str):
        return None
    if inner["dados"] is not None and not isinstance(inner["dados"], str):
        return None
    return inner


def _trusted_final_url(value: str | None) -> bool:
    if value is None:
        return False
    parsed = urlparse(value)
    endpoint = urlparse(ENET_PUBLIC_LIST_URL)
    return bool(
        parsed.scheme == "https"
        and parsed.hostname in _ALLOWED_HOSTS
        and parsed.path.casefold() == endpoint.path.casefold()
        and not parsed.query
        and not parsed.fragment
    )


def _normalize(value: str) -> str:
    replacements = str.maketrans("ÁÀÂÃÉÊÍÓÔÕÚÇ", "AAAAEEIOOOUC")
    return re.sub(r"\s+", " ", value.upper().translate(replacements)).strip()


def _version_tokens(value: str) -> tuple[int, ...]:
    versions: set[int] = set()
    for pattern in _VERSION_PATTERNS:
        for match in pattern.findall(value):
            parsed = int(match)
            if 0 < parsed <= 999:
                versions.add(parsed)
    return tuple(sorted(versions))
