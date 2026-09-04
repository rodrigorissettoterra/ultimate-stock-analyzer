from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable
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
_VERSION_FAMILIES = ("v1", "v2")
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
class Pillar3DASFNCatalogSample:
    version_family: str
    sha256: str
    size_bytes: int
    row_count: int
    observed_fields: tuple[str, ...]
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
    observed_catalog_samples: tuple[Pillar3DASFNCatalogSample, ...]
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
    schema_version: str = "0.1"

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
            "observed_catalog_samples": [
                {
                    **asdict(item),
                    "observed_fields": list(item.observed_fields),
                    "observed_versions": list(item.observed_versions),
                    "observed_resource_templates": list(
                        item.observed_resource_templates
                    ),
                    "reference_selector_tokens": list(
                        item.reference_selector_tokens
                    ),
                }
                for item in self.observed_catalog_samples
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
    catalog_payloads: Iterable[tuple[str, bytes]],
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

    samples = tuple(
        _catalog_sample(version_family, content)
        for version_family, content in catalog_payloads
    )
    if not samples:
        raise ValueError("catalog_payloads must contain live DASFN catalog samples")
    families = {sample.version_family for sample in samples}
    missing = set(_VERSION_FAMILIES) - families
    if missing:
        raise ValueError(
            "missing DASFN catalog samples for version families: "
            + ", ".join(sorted(missing))
        )

    observed_fields = {
        field for sample in samples for field in sample.observed_fields
    }
    revision_like = tuple(
        sorted(
            field for field in observed_fields if _looks_revision_like(field)
        )
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
        observed_catalog_samples=samples,
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


def _catalog_sample(
    version_family: str,
    content: bytes,
) -> Pillar3DASFNCatalogSample:
    normalized_family = version_family.strip().casefold()
    if normalized_family not in _VERSION_FAMILIES:
        raise ValueError("version_family must be v1 or v2")
    try:
        payload = json.loads(content)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("DASFN live catalog sample is not valid JSON") from error
    if not isinstance(payload, dict) or not isinstance(payload.get("value"), list):
        raise TypeError("DASFN live catalog sample must contain an OData value list")
    rows = payload["value"]
    if not rows:
        raise ValueError(
            f"DASFN live catalog sample {normalized_family} returned no rows"
        )
    if any(not isinstance(row, dict) for row in rows):
        raise TypeError("DASFN live catalog sample contains a non-object row")

    fields = tuple(sorted({str(key) for row in rows for key in row}))
    versions = tuple(
        sorted(
            {
                str(value).strip()
                for row in rows
                if (value := _value_case_insensitive(row, "Versao")) is not None
                and str(value).strip()
            }
        )
    )
    if not versions:
        raise ValueError("DASFN catalog sample exposes no Versao values")
    expected_prefix = normalized_family.removeprefix("v")
    if not any(version.startswith(expected_prefix) for version in versions):
        raise ValueError(
            f"DASFN catalog sample {normalized_family} has unexpected versions: "
            + ", ".join(versions)
        )

    api_values = {
        str(value).strip().casefold()
        for row in rows
        if (value := _value_case_insensitive(row, "Api")) is not None
    }
    if "pilar3" not in api_values:
        raise ValueError("DASFN catalog sample is not scoped to the pilar3 API")

    resources = tuple(
        sorted(
            {
                str(value).strip()
                for row in rows
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
    return Pillar3DASFNCatalogSample(
        version_family=normalized_family,
        sha256=hashlib.sha256(content).hexdigest(),
        size_bytes=len(content),
        row_count=len(rows),
        observed_fields=fields,
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
