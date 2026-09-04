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

_DASFN_CATALOG_HOST = "https://olinda.bcb.gov.br/"
_BCB_OPEN_DATA_HOST = "https://dadosabertos.bcb.gov.br/"
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
    catalog_sha256: str
    catalog_size_bytes: int
    catalog_row_count: int
    catalog_observed_fields: tuple[str, ...]
    version_observations: tuple[Pillar3DASFNVersionObservation, ...]
    revision_like_catalog_fields: tuple[str, ...]
    structured_reference_date_coverage_proven: bool
    catalog_links_collected_daily_by_bcb: bool
    institution_payloads_sampled: bool
    payload_publication_timestamp_proven: bool
    revision_history_proven: bool
    historical_vintage_query_proven: bool
    current_catalog_observation_point_in_time_from_collection: bool
    historical_replay_ready: bool
    bank_evidence_point_in_time_ready: bool
    readiness_promotion_allowed: bool
    blockers: tuple[str, ...]
    effect: str = "diagnostic_only_pillar3_dasfn_pit_source_no_readiness_change"
    schema_version: str = "0.2"

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
            "catalog_sha256": self.catalog_sha256,
            "catalog_size_bytes": self.catalog_size_bytes,
            "catalog_row_count": self.catalog_row_count,
            "catalog_observed_fields": list(self.catalog_observed_fields),
            "version_observations": [
                {
                    **asdict(item),
                    "observed_versions": list(item.observed_versions),
                    "observed_resource_templates": list(
                        item.observed_resource_templates
                    ),
                    "reference_selector_tokens": list(
                        item.reference_selector_tokens
                    ),
                }
                for item in self.version_observations
            ],
            "revision_like_catalog_fields": list(
                self.revision_like_catalog_fields
            ),
            "structured_reference_date_coverage_proven": (
                self.structured_reference_date_coverage_proven
            ),
            "catalog_links_collected_daily_by_bcb": (
                self.catalog_links_collected_daily_by_bcb
            ),
            "institution_payloads_sampled": self.institution_payloads_sampled,
            "payload_publication_timestamp_proven": (
                self.payload_publication_timestamp_proven
            ),
            "revision_history_proven": self.revision_history_proven,
            "historical_vintage_query_proven": (
                self.historical_vintage_query_proven
            ),
            "current_catalog_observation_point_in_time_from_collection": (
                self.current_catalog_observation_point_in_time_from_collection
            ),
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
    catalog_content: bytes,
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

    rows = _catalog_rows(catalog_content)
    fields = tuple(sorted({str(key) for row in rows for key in row}))
    api_values = {
        str(value).strip().casefold()
        for row in rows
        if (value := _value_case_insensitive(row, "Api")) is not None
    }
    if api_values != {"pilar3"}:
        raise ValueError("DASFN catalog sample must be scoped only to the pilar3 API")

    observations = tuple(
        _version_observation(rows, family, prefix)
        for family, prefix in (("v1", "1"), ("v2", "2"))
    )
    revision_like = tuple(
        sorted(field for field in fields if _looks_revision_like(field))
    )
    blockers = (
        BANK_EVIDENCE_NOT_POINT_IN_TIME,
        PILLAR3_DASFN_HISTORICAL_VINTAGE_QUERY_UNPROVEN,
        PILLAR3_DASFN_PAYLOAD_PUBLICATION_TIMESTAMP_UNPROVEN,
        PILLAR3_DASFN_REVISION_HISTORY_UNPROVEN,
        PILLAR3_DASFN_STRUCTURED_COVERAGE_GAP,
    )
    return BCBPillar3DASFNPITSourceAudit(
        collected_at=collected_at,
        catalog_source_url=catalog_source_url,
        v1_dataset_url=v1_dataset_url,
        v2_dataset_url=v2_dataset_url,
        structured_coverage=official_structured_coverage_contract(),
        catalog_sha256=hashlib.sha256(catalog_content).hexdigest(),
        catalog_size_bytes=len(catalog_content),
        catalog_row_count=len(rows),
        catalog_observed_fields=fields,
        version_observations=observations,
        revision_like_catalog_fields=revision_like,
        structured_reference_date_coverage_proven=True,
        catalog_links_collected_daily_by_bcb=True,
        institution_payloads_sampled=False,
        payload_publication_timestamp_proven=False,
        revision_history_proven=False,
        historical_vintage_query_proven=False,
        current_catalog_observation_point_in_time_from_collection=True,
        historical_replay_ready=False,
        bank_evidence_point_in_time_ready=False,
        readiness_promotion_allowed=False,
        blockers=blockers,
    )


def _catalog_rows(content: bytes) -> tuple[dict[str, Any], ...]:
    if not content.strip():
        raise ValueError("DASFN live catalog sample must not be empty")
    try:
        payload = json.loads(content)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("DASFN live catalog sample is not valid JSON") from error
    if not isinstance(payload, dict) or not isinstance(payload.get("value"), list):
        raise TypeError("DASFN live catalog sample must contain an OData value list")
    rows = payload["value"]
    if not rows:
        raise ValueError("DASFN live catalog sample returned no rows")
    if any(not isinstance(row, dict) for row in rows):
        raise TypeError("DASFN live catalog sample contains a non-object row")
    return tuple(rows)


def _version_observation(
    rows: tuple[dict[str, Any], ...],
    version_family: str,
    prefix: str,
) -> Pillar3DASFNVersionObservation:
    matching = tuple(
        row
        for row in rows
        if (
            (value := _value_case_insensitive(row, "Versao")) is not None
            and str(value).strip().startswith(prefix)
        )
    )
    if not matching:
        raise ValueError(
            f"DASFN catalog exposes no Pillar 3 {version_family} resources"
        )
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
