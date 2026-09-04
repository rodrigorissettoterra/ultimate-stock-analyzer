from __future__ import annotations

import json
from datetime import UTC, date, datetime

import pytest

from ultimate_stock_analyzer.backtesting.bcb_pillar3_dasfn_pit_source_audit import (
    BANK_EVIDENCE_NOT_POINT_IN_TIME,
    PILLAR3_DASFN_CATALOG_CONTRACT_UNUSABLE,
    PILLAR3_DASFN_CATALOG_ENDPOINT_UNAVAILABLE,
    PILLAR3_DASFN_HISTORICAL_VINTAGE_QUERY_UNPROVEN,
    PILLAR3_DASFN_PAYLOAD_PUBLICATION_TIMESTAMP_UNPROVEN,
    PILLAR3_DASFN_PILAR3_QUERY_UNAVAILABLE,
    PILLAR3_DASFN_REVISION_HISTORY_UNPROVEN,
    PILLAR3_DASFN_STRUCTURED_COVERAGE_GAP,
    PILLAR3_DASFN_VERSION_FAMILY_NOT_OBSERVED,
    Pillar3DASFNCatalogProbeInput,
    audit_bcb_pillar3_dasfn_pit_source,
    official_structured_coverage_contract,
)

CATALOG_URL = (
    "https://olinda.bcb.gov.br/olinda/servico/"
    "DASFN/versao/v1/odata/Recursos"
)
V1_DATASET_URL = "https://dadosabertos.bcb.gov.br/dataset/pilar3"
V2_DATASET_URL = "https://dadosabertos.bcb.gov.br/dataset/pilar3-v2"


def _catalog_payload(*, extra_field: str | None = None, v2: bool = True) -> bytes:
    rows: list[dict[str, object]] = [
        {
            "Api": "pilar3",
            "Versao": "1.2.0",
            "Recurso": "/km1/{semestre}",
            "Url": "https://example.invalid/pillar3/v1",
        }
    ]
    if v2:
        rows.append(
            {
                "Api": "pilar3",
                "Versao": "2.0.0",
                "Recurso": "/km1/v2/{trimestre}",
                "Url": "https://example.invalid/pillar3/v2",
            }
        )
    if extra_field:
        rows[0][extra_field] = "2026-09-04"
    return json.dumps({"value": rows}).encode()


def _http_probe(name: str, content: bytes, status: int = 200):
    suffix = "?$filter=Api%20eq%20'pilar3'" if name == "pillar3_query" else ""
    return Pillar3DASFNCatalogProbeInput(
        name=name,
        requested_url=f"{CATALOG_URL}{suffix}",
        final_url=f"{CATALOG_URL}{suffix}",
        status_code=status,
        content_type="application/json",
        content=content,
    )


def _audit(
    *,
    base_status: int = 200,
    query_status: int = 200,
    query_content: bytes | None = None,
):
    return audit_bcb_pillar3_dasfn_pit_source(
        probes=(
            _http_probe("base", b'{"value":[]}', base_status),
            _http_probe(
                "pillar3_query",
                query_content if query_content is not None else _catalog_payload(),
                query_status,
            ),
        ),
        collected_at=datetime(2026, 9, 4, tzinfo=UTC),
        catalog_source_url=CATALOG_URL,
        v1_dataset_url=V1_DATASET_URL,
        v2_dataset_url=V2_DATASET_URL,
    )


def test_official_structured_coverage_contract_preserves_bcb_boundaries() -> None:
    coverage = official_structured_coverage_contract()

    assert coverage.v1_max_reference_date == date(2023, 6, 30)
    assert coverage.v2_min_reference_date == date(2025, 12, 31)
    assert coverage.pdf_only_interval_start_exclusive == date(2023, 6, 30)
    assert coverage.pdf_only_interval_end_exclusive == date(2025, 12, 31)


def test_http_400_is_preserved_as_source_evidence_and_fails_closed() -> None:
    audit = _audit(base_status=400, query_status=400, query_content=b"bad request")

    evidence = {item.name: item for item in audit.catalog_probes}
    assert evidence["base"].status_code == 400
    assert evidence["pillar3_query"].status_code == 400
    assert evidence["pillar3_query"].size_bytes == len(b"bad request")
    assert len(evidence["pillar3_query"].sha256 or "") == 64
    assert not audit.catalog_endpoint_available
    assert not audit.pillar3_query_available
    assert PILLAR3_DASFN_CATALOG_ENDPOINT_UNAVAILABLE in audit.blockers
    assert PILLAR3_DASFN_PILAR3_QUERY_UNAVAILABLE in audit.blockers
    assert not audit.readiness_promotion_allowed


def test_successful_catalog_contract_groups_v1_and_v2_without_pit_promotion() -> None:
    audit = _audit()
    observations = {item.version_family: item for item in audit.version_observations}

    assert audit.catalog_endpoint_available
    assert audit.pillar3_query_available
    assert audit.catalog_contract_usable
    assert set(observations) == {"v1", "v2"}
    assert observations["v1"].observed_versions == ("1.2.0",)
    assert observations["v2"].observed_versions == ("2.0.0",)
    assert observations["v1"].reference_selector_tokens == ("semestre",)
    assert observations["v2"].reference_selector_tokens == ("trimestre",)
    assert not audit.historical_vintage_query_proven
    assert not audit.bank_evidence_point_in_time_ready


def test_baseline_pit_blockers_are_invariant_even_when_catalog_is_usable() -> None:
    audit = _audit()
    required = {
        BANK_EVIDENCE_NOT_POINT_IN_TIME,
        PILLAR3_DASFN_HISTORICAL_VINTAGE_QUERY_UNPROVEN,
        PILLAR3_DASFN_PAYLOAD_PUBLICATION_TIMESTAMP_UNPROVEN,
        PILLAR3_DASFN_REVISION_HISTORY_UNPROVEN,
        PILLAR3_DASFN_STRUCTURED_COVERAGE_GAP,
    }

    assert required.issubset(audit.blockers)
    assert audit.structured_reference_date_coverage_documented
    assert not audit.institution_payloads_sampled
    assert not audit.historical_replay_ready
    assert not audit.readiness_promotion_allowed


def test_revision_like_catalog_field_never_proves_payload_revision_history() -> None:
    audit = _audit(query_content=_catalog_payload(extra_field="DataUltimaAtualizacao"))

    assert "DataUltimaAtualizacao" in audit.revision_like_catalog_fields
    assert "Versao" in audit.revision_like_catalog_fields
    assert not audit.payload_publication_timestamp_proven
    assert not audit.revision_history_proven


def test_successful_but_unusable_catalog_payload_adds_contract_blocker() -> None:
    audit = _audit(query_content=json.dumps({"value": {}}).encode())

    assert audit.pillar3_query_available
    assert not audit.catalog_contract_usable
    assert PILLAR3_DASFN_CATALOG_CONTRACT_UNUSABLE in audit.blockers


def test_missing_version_family_is_observed_without_throwing_away_evidence() -> None:
    audit = _audit(query_content=_catalog_payload(v2=False))

    assert audit.pillar3_query_available
    assert not audit.catalog_contract_usable
    assert len(audit.version_observations) == 1
    assert audit.version_observations[0].version_family == "v1"
    assert PILLAR3_DASFN_VERSION_FAMILY_NOT_OBSERVED in audit.blockers


def test_transport_error_is_preserved_without_fabricating_http_provenance() -> None:
    transport = Pillar3DASFNCatalogProbeInput(
        name="base",
        requested_url=CATALOG_URL,
        final_url=None,
        status_code=None,
        content_type=None,
        content=None,
        transport_error="ReadTimeout: timed out",
    )
    audit = audit_bcb_pillar3_dasfn_pit_source(
        probes=(transport, _http_probe("pillar3_query", _catalog_payload())),
        collected_at=datetime(2026, 9, 4, tzinfo=UTC),
        catalog_source_url=CATALOG_URL,
        v1_dataset_url=V1_DATASET_URL,
        v2_dataset_url=V2_DATASET_URL,
    )

    base = audit.catalog_probes[0]
    assert base.status_code is None
    assert base.sha256 is None
    assert base.size_bytes == 0
    assert base.transport_error == "ReadTimeout: timed out"
    assert PILLAR3_DASFN_CATALOG_ENDPOINT_UNAVAILABLE in audit.blockers


def test_validation_and_serialization_keep_auditable_boundary() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        audit_bcb_pillar3_dasfn_pit_source(
            probes=(
                _http_probe("base", b"{}"),
                _http_probe("pillar3_query", _catalog_payload()),
            ),
            collected_at=datetime(2026, 9, 4),
            catalog_source_url=CATALOG_URL,
            v1_dataset_url=V1_DATASET_URL,
            v2_dataset_url=V2_DATASET_URL,
        )

    payload = _audit(base_status=400, query_status=400).to_dict()
    assert payload["schema_version"] == "0.3"
    assert payload["collected_at"] == "2026-09-04T00:00:00+00:00"
    assert payload["structured_coverage"]["v1_max_reference_date"] == "2023-06-30"
    assert payload["structured_coverage"]["v2_min_reference_date"] == "2025-12-31"
    assert payload["bank_evidence_point_in_time_ready"] is False
