from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from datetime import date, datetime
from typing import Any

BANK_EVIDENCE_NOT_POINT_IN_TIME = "BANK_EVIDENCE_NOT_POINT_IN_TIME"
PILLAR3_DASFN_PAYLOAD_PUBLICATION_TIMESTAMP_UNPROVEN = (
    "PILLAR3_DASFN_PAYLOAD_PUBLICATION_TIMESTAMP_UNPROVEN"
)
PILLAR3_DASFN_REVISION_HISTORY_UNPROVEN = (
    "PILLAR3_DASFN_REVISION_HISTORY_UNPROVEN"
)
PILLAR3_DASFN_HISTORICAL_VINTAGE_QUERY_UNPROVEN = (
    "PILLAR3_DASFN_HISTORICAL_VINTAGE_QUERY_UNPROVEN"
)
PILLAR3_DASFN_STRUCTURED_COVERAGE_GAP = (
    "PILLAR3_DASFN_STRUCTURED_COVERAGE_GAP"
)
PILLAR3_DASFN_CATALOG_ENDPOINT_UNAVAILABLE = (
    "PILLAR3_DASFN_CATALOG_ENDPOINT_UNAVAILABLE"
)
PILLAR3_DASFN_PILAR3_QUERY_UNAVAILABLE = (
    "PILLAR3_DASFN_PILAR3_QUERY_UNAVAILABLE"
)
PILLAR3_DASFN_CATALOG_CONTRACT_UNUSABLE = (
    "PILLAR3_DASFN_CATALOG_CONTRACT_UNUSABLE"
)
PILLAR3_DASFN_VERSION_FAMILY_NOT_OBSERVED = (
    "PILLAR3_DASFN_VERSION_FAMILY_NOT_OBSERVED"
)
PILLAR3_DASFN_FINAL_URL_UNTRUSTED = "PILLAR3_DASFN_FINAL_URL_UNTRUSTED"

_DASFN_CATALOG_HOST = "https://olinda.bcb.gov.br/"
_BCB_OPEN_DATA_HOST = "https://dadosabertos.bcb.gov.br/"
_REQUIRED_CENTRAL_RESOURCE_FIELDS = (
    "Api",
    "Versao",
    "CnpjInstituicao",
    "Recurso",
    "URLDados",
)
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
_REFERENCE_TOKEN = re.compile(r"\{([^{}]+)\}")


@dataclass(frozen=True, slots=True)
class Pillar3DASFNStructuredCoverage:
    v1_max_reference_date: date
    v2_min_reference_date: date
    pdf_only_interval_start_exclusive: date
    pdf_only_interval_end_exclusive: date


@dataclass(frozen=True, slots=True)
class Pillar3DASFNCatalogProbeInput:
    name: str
    requested_url: str
    final_url: str | None
    status_code: int | None
    content_type: str | None
    content: bytes | None
    transport_error: str | None = None


@dataclass(frozen=True, slots=True)
class Pillar3DASFNCatalogProbeEvidence:
    name: str
    requested_url: str
    final_url: str | None
    status_code: int | None
    content_type: str | None
    sha256: str | None
    size_bytes: int
    transport_error: str | None
    http_success: bool


@dataclass(frozen=True, slots=True)
class Pillar3DASFNVersionObservation:
    version_family: str
    row_count: int
    observed_versions: tuple[str, ...]
    observed_resource_templates: tuple[str, ...]
    reference_selector_tokens: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class BCBPillar3DASFNPITSourceAudit:
    collected_at: datetime
    catalog_source_url: str
    v1_dataset_url: str
    v2_dataset_url: str
    structured_coverage: Pillar3DASFNStructuredCoverage
    catalog_probes: tuple[Pillar3DASFNCatalogProbeEvidence, ...]
    pillar3_query_observed_fields: tuple[str, ...]
    version_observations: tuple[Pillar3DASFNVersionObservation, ...]
    revision_like_catalog_fields: tuple[str, ...]
    structured_reference_date_coverage_documented: bool
    catalog_endpoint_available: bool
    pillar3_query_available: bool
    catalog_contract_usable: bool
    institution_payloads_sampled: bool
    payload_publication_timestamp_proven: bool
    revision_history_proven: bool
    historical_vintage_query_proven: bool
    historical_replay_ready: bool
    bank_evidence_point_in_time_ready: bool
    readiness_promotion_allowed: bool
    blockers: tuple[str, ...]
    effect: str = "diagnostic_only_pillar3_dasfn_pit_source_no_readiness_change"
    schema_version: str = "0.4"

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "effect": self.effect,
            "collected_at": self.collected_at.isoformat(),
            "catalog_source_url": self.catalog_source_url,
            "v1_dataset_url": self.v1_dataset_url,
            "v2_dataset_url": self.v2_dataset_url,
            "structured_coverage": {
                "v1_max_reference_date": (
                    self.structured_coverage.v1_max_reference_date.isoformat()
                ),
                "v2_min_reference_date": (
                    self.structured_coverage.v2_min_reference_date.isoformat()
                ),
                "pdf_only_interval_start_exclusive": (
                    self.structured_coverage
                    .pdf_only_interval_start_exclusive.isoformat()
                ),
                "pdf_only_interval_end_exclusive": (
                    self.structured_coverage.pdf_only_interval_end_exclusive.isoformat()
                ),
            },
            "catalog_probes": [asdict(item) for item in self.catalog_probes],
            "pillar3_query_observed_fields": list(self.pillar3_query_observed_fields),
            "version_observations": [
                {
                    **asdict(item),
                    "observed_versions": list(item.observed_versions),
                    "observed_resource_templates": list(
                        item.observed_resource_templates
                    ),
                    "reference_selector_tokens": list(item.reference_selector_tokens),
                }
                for item in self.version_observations
            ],
            "revision_like_catalog_fields": list(self.revision_like_catalog_fields),
            "structured_reference_date_coverage_documented": (
                self.structured_reference_date_coverage_documented
            ),
            "catalog_endpoint_available": self.catalog_endpoint_available,
            "pillar3_query_available": self.pillar3_query_available,
            "catalog_contract_usable": self.catalog_contract_usable,
            "institution_payloads_sampled": self.institution_payloads_sampled,
            "payload_publication_timestamp_proven": (
                self.payload_publication_timestamp_proven
            ),
            "revision_history_proven": self.revision_history_proven,
            "historical_vintage_query_proven": self.historical_vintage_query_proven,
            "historical_replay_ready": self.historical_replay_ready,
            "bank_evidence_point_in_time_ready": (
                self.bank_evidence_point_in_time_ready
            ),
            "readiness_promotion_allowed": self.readiness_promotion_allowed,
            "blockers": list(self.blockers),
        }


def official_structured_coverage_contract() -> Pillar3DASFNStructuredCoverage:
    return Pillar3DASFNStructuredCoverage(
        v1_max_reference_date=date(2023, 6, 30),
        v2_min_reference_date=date(2025, 12, 31),
        pdf_only_interval_start_exclusive=date(2023, 6, 30),
        pdf_only_interval_end_exclusive=date(2025, 12, 31),
    )


def audit_bcb_pillar3_dasfn_pit_source(
    *,
    probes: tuple[Pillar3DASFNCatalogProbeInput, ...]
    | list[Pillar3DASFNCatalogProbeInput],
    collected_at: datetime,
    catalog_source_url: str,
    v1_dataset_url: str,
    v2_dataset_url: str,
) -> BCBPillar3DASFNPITSourceAudit:
    if collected_at.tzinfo is None or collected_at.utcoffset() is None:
        raise ValueError("collected_at must be timezone-aware")
    if not catalog_source_url.startswith(_DASFN_CATALOG_HOST):
        raise ValueError("catalog_source_url must use the official BCB Olinda host")
    for dataset_url in (v1_dataset_url, v2_dataset_url):
        if not dataset_url.startswith(_BCB_OPEN_DATA_HOST):
            raise ValueError(
                "Pillar 3 dataset URLs must use the official BCB open-data host"
            )

    normalized_probes = tuple(probes)
    by_name = {probe.name: probe for probe in normalized_probes}
    if (
        set(by_name) != {"base", "pillar3_query"}
        or len(by_name) != len(normalized_probes)
    ):
        raise ValueError("probes must contain exactly base and pillar3_query")
    if any(
        not probe.requested_url.startswith(_DASFN_CATALOG_HOST)
        for probe in normalized_probes
    ):
        raise ValueError("all catalog probes must use the official BCB Olinda host")

    evidence = tuple(
        _probe_evidence(by_name[name]) for name in ("base", "pillar3_query")
    )
    base_available = _trusted_http_success(by_name["base"])
    query_available = _trusted_http_success(by_name["pillar3_query"])
    blockers = {
        BANK_EVIDENCE_NOT_POINT_IN_TIME,
        PILLAR3_DASFN_HISTORICAL_VINTAGE_QUERY_UNPROVEN,
        PILLAR3_DASFN_PAYLOAD_PUBLICATION_TIMESTAMP_UNPROVEN,
        PILLAR3_DASFN_REVISION_HISTORY_UNPROVEN,
        PILLAR3_DASFN_STRUCTURED_COVERAGE_GAP,
    }
    if any(
        _http_success(probe) and not _final_url_trusted(probe)
        for probe in normalized_probes
    ):
        blockers.add(PILLAR3_DASFN_FINAL_URL_UNTRUSTED)
    if not base_available:
        blockers.add(PILLAR3_DASFN_CATALOG_ENDPOINT_UNAVAILABLE)
    if not query_available:
        blockers.add(PILLAR3_DASFN_PILAR3_QUERY_UNAVAILABLE)

    fields: tuple[str, ...] = ()
    observations: tuple[Pillar3DASFNVersionObservation, ...] = ()
    contract_usable = False
    query = by_name["pillar3_query"]
    if query_available:
        rows = _try_catalog_rows(query.content)
        if rows is None:
            blockers.add(PILLAR3_DASFN_CATALOG_CONTRACT_UNUSABLE)
        else:
            fields = tuple(sorted({str(key) for row in rows for key in row}))
            if not _all_rows_match_central_resource_contract(rows):
                blockers.add(PILLAR3_DASFN_CATALOG_CONTRACT_UNUSABLE)
            else:
                version_items: list[Pillar3DASFNVersionObservation] = []
                missing_family = False
                for family, prefix in (("v1", "1"), ("v2", "2")):
                    observation = _version_observation(rows, family, prefix)
                    if observation is None:
                        missing_family = True
                    else:
                        version_items.append(observation)
                observations = tuple(version_items)
                if missing_family:
                    blockers.add(PILLAR3_DASFN_VERSION_FAMILY_NOT_OBSERVED)
                elif sum(item.row_count for item in observations) != len(rows):
                    blockers.add(PILLAR3_DASFN_CATALOG_CONTRACT_UNUSABLE)
                else:
                    contract_usable = True

    revision_like = tuple(
        sorted(field for field in fields if _looks_revision_like(field))
    )
    return BCBPillar3DASFNPITSourceAudit(
        collected_at=collected_at,
        catalog_source_url=catalog_source_url,
        v1_dataset_url=v1_dataset_url,
        v2_dataset_url=v2_dataset_url,
        structured_coverage=official_structured_coverage_contract(),
        catalog_probes=evidence,
        pillar3_query_observed_fields=fields,
        version_observations=observations,
        revision_like_catalog_fields=revision_like,
        structured_reference_date_coverage_documented=True,
        catalog_endpoint_available=base_available,
        pillar3_query_available=query_available,
        catalog_contract_usable=contract_usable,
        institution_payloads_sampled=False,
        payload_publication_timestamp_proven=False,
        revision_history_proven=False,
        historical_vintage_query_proven=False,
        historical_replay_ready=False,
        bank_evidence_point_in_time_ready=False,
        readiness_promotion_allowed=False,
        blockers=tuple(sorted(blockers)),
    )


def _probe_evidence(
    probe: Pillar3DASFNCatalogProbeInput,
) -> Pillar3DASFNCatalogProbeEvidence:
    if probe.status_code is None:
        if probe.transport_error is None:
            raise ValueError("probe without HTTP status must preserve transport_error")
        if probe.content is not None:
            raise ValueError("transport-error probe must not contain response content")
        sha256 = None
        size_bytes = 0
    else:
        if not (100 <= probe.status_code <= 599):
            raise ValueError("HTTP status code must be between 100 and 599")
        if probe.transport_error is not None:
            raise ValueError("HTTP response probe must not contain transport_error")
        content = probe.content or b""
        sha256 = hashlib.sha256(content).hexdigest()
        size_bytes = len(content)
    return Pillar3DASFNCatalogProbeEvidence(
        name=probe.name,
        requested_url=probe.requested_url,
        final_url=probe.final_url,
        status_code=probe.status_code,
        content_type=probe.content_type,
        sha256=sha256,
        size_bytes=size_bytes,
        transport_error=probe.transport_error,
        http_success=_http_success(probe),
    )


def _http_success(probe: Pillar3DASFNCatalogProbeInput) -> bool:
    return probe.status_code is not None and 200 <= probe.status_code < 300


def _final_url_trusted(probe: Pillar3DASFNCatalogProbeInput) -> bool:
    return probe.final_url is not None and probe.final_url.startswith(_DASFN_CATALOG_HOST)


def _trusted_http_success(probe: Pillar3DASFNCatalogProbeInput) -> bool:
    return _http_success(probe) and _final_url_trusted(probe)


def _try_catalog_rows(content: bytes | None) -> tuple[dict[str, Any], ...] | None:
    if not content:
        return None
    try:
        payload = json.loads(content)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict) or not isinstance(payload.get("value"), list):
        return None
    rows = payload["value"]
    if not rows or any(not isinstance(row, dict) for row in rows):
        return None
    return tuple(rows)


def _all_rows_match_central_resource_contract(
    rows: tuple[dict[str, Any], ...],
) -> bool:
    for row in rows:
        values = {
            field: _value_case_insensitive(row, field)
            for field in _REQUIRED_CENTRAL_RESOURCE_FIELDS
        }
        if any(value is None or not str(value).strip() for value in values.values()):
            return False
        if str(values["Api"]).strip().casefold() != "pilar3":
            return False
        cnpj = str(values["CnpjInstituicao"]).strip()
        if len(cnpj) != 14 or not cnpj.isdigit():
            return False
        version = str(values["Versao"]).strip()
        if not (_version_in_family(version, "1") or _version_in_family(version, "2")):
            return False
    return True


def _version_in_family(version: str, prefix: str) -> bool:
    return version == prefix or version.startswith(f"{prefix}.")


def _version_observation(
    rows: tuple[dict[str, Any], ...],
    version_family: str,
    prefix: str,
) -> Pillar3DASFNVersionObservation | None:
    matching = tuple(
        row
        for row in rows
        if (
            (value := _value_case_insensitive(row, "Versao")) is not None
            and _version_in_family(str(value).strip(), prefix)
        )
    )
    if not matching:
        return None
    versions = tuple(
        sorted(
            {
                str(value).strip()
                for row in matching
                if (value := _value_case_insensitive(row, "Versao")) is not None
                and str(value).strip()
            }
        )
    )
    resources = tuple(
        sorted(
            {
                str(value).strip()
                for row in matching
                if (value := _value_case_insensitive(row, "Recurso")) is not None
                and str(value).strip()
            }
        )
    )
    selectors = tuple(
        sorted(
            {
                token.strip().casefold()
                for resource in resources
                for token in _REFERENCE_TOKEN.findall(resource)
                if token.strip()
            }
        )
    )
    return Pillar3DASFNVersionObservation(
        version_family=version_family,
        row_count=len(matching),
        observed_versions=versions,
        observed_resource_templates=resources,
        reference_selector_tokens=selectors,
    )


def _value_case_insensitive(row: dict[str, Any], field: str) -> Any:
    expected = field.casefold()
    for key, value in row.items():
        if str(key).casefold() == expected:
            return value
    return None


def _looks_revision_like(name: str) -> bool:
    normalized = (
        name.casefold()
        .replace("_", "")
        .replace("-", "")
        .replace(" ", "")
    )
    return any(token in normalized for token in _REVISION_TOKENS)
