from __future__ import annotations

import hashlib
import json
from calendar import monthrange
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta
from typing import Any
from xml.etree import ElementTree

BANK_EVIDENCE_NOT_POINT_IN_TIME = "BANK_EVIDENCE_NOT_POINT_IN_TIME"
IFDATA_ROW_PUBLICATION_TIMESTAMP_UNAVAILABLE = (
    "IFDATA_ROW_PUBLICATION_TIMESTAMP_UNAVAILABLE"
)
IFDATA_REVISION_HISTORY_UNAVAILABLE = "IFDATA_REVISION_HISTORY_UNAVAILABLE"
IFDATA_HISTORICAL_VINTAGE_QUERY_UNAVAILABLE = (
    "IFDATA_HISTORICAL_VINTAGE_QUERY_UNAVAILABLE"
)

_QUARTER_PUBLICATION_DELAY_DAYS = {3: 60, 6: 60, 9: 60, 12: 90}
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
class IFDataInitialReleaseEvidence:
    ano_mes: int
    reference_date: date
    publication_delay_days: int
    contractual_initial_release_date: date


@dataclass(frozen=True, slots=True)
class IFDataObservedSample:
    ano_mes: int
    kind: str
    sha256: str
    size_bytes: int
    row_count: int
    observed_fields: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class BCBIFDataPITSourceAudit:
    collected_at: datetime
    source_dataset_url: str
    metadata_sha256: str
    metadata_size_bytes: int
    metadata_property_names: tuple[str, ...]
    metadata_parameter_names: tuple[str, ...]
    revision_like_metadata_names: tuple[str, ...]
    initial_release_evidence: tuple[IFDataInitialReleaseEvidence, ...]
    observed_samples: tuple[IFDataObservedSample, ...]
    initial_publication_timing_proven: bool
    row_level_publication_timestamp_proven: bool
    revision_history_proven: bool
    historical_vintage_query_proven: bool
    current_observation_point_in_time_from_collection: bool
    historical_replay_ready: bool
    bank_evidence_point_in_time_ready: bool
    readiness_promotion_allowed: bool
    blockers: tuple[str, ...]
    effect: str = "diagnostic_only_ifdata_pit_source_no_readiness_change"
    schema_version: str = "0.1"

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["collected_at"] = self.collected_at.isoformat()
        payload["metadata_property_names"] = list(self.metadata_property_names)
        payload["metadata_parameter_names"] = list(self.metadata_parameter_names)
        payload["revision_like_metadata_names"] = list(
            self.revision_like_metadata_names
        )
        payload["initial_release_evidence"] = [
            {
                "ano_mes": item.ano_mes,
                "reference_date": item.reference_date.isoformat(),
                "publication_delay_days": item.publication_delay_days,
                "contractual_initial_release_date": (
                    item.contractual_initial_release_date.isoformat()
                ),
            }
            for item in self.initial_release_evidence
        ]
        payload["observed_samples"] = [
            {
                **asdict(item),
                "observed_fields": list(item.observed_fields),
            }
            for item in self.observed_samples
        ]
        payload["blockers"] = list(self.blockers)
        return payload


def contractual_initial_release_evidence(
    ano_mes: int,
) -> IFDataInitialReleaseEvidence:
    year, month = divmod(ano_mes, 100)
    if year < 2000 or month not in _QUARTER_PUBLICATION_DELAY_DAYS:
        raise ValueError(
            "IFData PIT audit accepts quarterly reference periods in AAAAMM format"
        )
    reference_date = date(year, month, monthrange(year, month)[1])
    delay_days = _QUARTER_PUBLICATION_DELAY_DAYS[month]
    return IFDataInitialReleaseEvidence(
        ano_mes=ano_mes,
        reference_date=reference_date,
        publication_delay_days=delay_days,
        contractual_initial_release_date=reference_date + timedelta(days=delay_days),
    )


def audit_bcb_ifdata_pit_source(
    *,
    metadata_content: bytes,
    sample_payloads: Iterable[tuple[int, str, bytes]],
    requested_ano_mes: Iterable[int],
    collected_at: datetime,
    source_dataset_url: str,
) -> BCBIFDataPITSourceAudit:
    if not source_dataset_url.startswith("https://dadosabertos.bcb.gov.br/"):
        raise ValueError("source_dataset_url must use the official BCB open-data host")
    if not metadata_content.strip():
        raise ValueError("IFData OData metadata must not be empty")

    properties, parameters = _metadata_names(metadata_content)
    periods = tuple(dict.fromkeys(requested_ano_mes))
    if not periods:
        raise ValueError("requested_ano_mes must contain at least one reference period")
    initial_release = tuple(
        contractual_initial_release_evidence(ano_mes) for ano_mes in periods
    )

    samples = tuple(
        _sample_evidence(ano_mes, kind, content)
        for ano_mes, kind, content in sample_payloads
    )
    if not samples:
        raise ValueError("sample_payloads must contain at least one live IFData sample")
    sampled_periods = {item.ano_mes for item in samples}
    missing_periods = set(periods) - sampled_periods
    if missing_periods:
        raise ValueError(
            "missing IFData live samples for requested periods: "
            + ", ".join(str(item) for item in sorted(missing_periods))
        )

    metadata_names = {*properties, *parameters}
    revision_like = tuple(
        sorted(name for name in metadata_names if _looks_revision_like(name))
    )

    # BCB documents the initial quarterly publication delay, but the public IFData
    # OData contract does not expose an as-of/vintage selector or a revision ledger.
    # Metadata names that merely look temporal are therefore evidence to inspect,
    # never automatic proof of revision-aware replay semantics.
    blockers = (
        BANK_EVIDENCE_NOT_POINT_IN_TIME,
        IFDATA_HISTORICAL_VINTAGE_QUERY_UNAVAILABLE,
        IFDATA_REVISION_HISTORY_UNAVAILABLE,
        IFDATA_ROW_PUBLICATION_TIMESTAMP_UNAVAILABLE,
    )
    return BCBIFDataPITSourceAudit(
        collected_at=collected_at,
        source_dataset_url=source_dataset_url,
        metadata_sha256=hashlib.sha256(metadata_content).hexdigest(),
        metadata_size_bytes=len(metadata_content),
        metadata_property_names=properties,
        metadata_parameter_names=parameters,
        revision_like_metadata_names=revision_like,
        initial_release_evidence=initial_release,
        observed_samples=samples,
        initial_publication_timing_proven=True,
        row_level_publication_timestamp_proven=False,
        revision_history_proven=False,
        historical_vintage_query_proven=False,
        current_observation_point_in_time_from_collection=True,
        historical_replay_ready=False,
        bank_evidence_point_in_time_ready=False,
        readiness_promotion_allowed=False,
        blockers=blockers,
    )


def _metadata_names(content: bytes) -> tuple[tuple[str, ...], tuple[str, ...]]:
    try:
        root = ElementTree.fromstring(content)
    except ElementTree.ParseError as error:
        raise ValueError("IFData OData metadata is not valid XML") from error

    properties: set[str] = set()
    parameters: set[str] = set()
    for element in root.iter():
        local_name = element.tag.rsplit("}", 1)[-1]
        name = element.attrib.get("Name")
        if not name:
            continue
        if local_name == "Property":
            properties.add(name)
        elif local_name == "Parameter":
            parameters.add(name)
    if not properties:
        raise ValueError("IFData OData metadata exposes no entity properties")
    if not parameters:
        raise ValueError("IFData OData metadata exposes no function parameters")
    return tuple(sorted(properties)), tuple(sorted(parameters))


def _sample_evidence(ano_mes: int, kind: str, content: bytes) -> IFDataObservedSample:
    if not kind.strip():
        raise ValueError("IFData sample kind must not be empty")
    try:
        payload = json.loads(content)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("IFData live sample is not valid JSON") from error
    if not isinstance(payload, dict) or not isinstance(payload.get("value"), list):
        raise TypeError("IFData live sample must contain an OData value list")
    rows = payload["value"]
    if not rows:
        raise ValueError(f"IFData live sample {kind}:{ano_mes} returned no rows")
    if any(not isinstance(row, dict) for row in rows):
        raise TypeError("IFData live sample contains a non-object row")
    fields = tuple(sorted({str(key) for row in rows for key in row}))
    return IFDataObservedSample(
        ano_mes=ano_mes,
        kind=kind.strip(),
        sha256=hashlib.sha256(content).hexdigest(),
        size_bytes=len(content),
        row_count=len(rows),
        observed_fields=fields,
    )


def _looks_revision_like(name: str) -> bool:
    normalized = (
        name.casefold()
        .replace("_", "")
        .replace("-", "")
        .replace(" ", "")
    )
    return any(token in normalized for token in _REVISION_TOKENS)
