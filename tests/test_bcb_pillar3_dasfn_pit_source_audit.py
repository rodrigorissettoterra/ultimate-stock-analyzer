from __future__ import annotations

import json
from datetime import UTC, date, datetime

import pytest

from ultimate_stock_analyzer.backtesting.bcb_pillar3_dasfn_pit_source_audit import (
    BANK_EVIDENCE_NOT_POINT_IN_TIME,
    PILLAR3_DASFN_HISTORICAL_VINTAGE_QUERY_UNPROVEN,
    PILLAR3_DASFN_PAYLOAD_PUBLICATION_TIMESTAMP_UNPROVEN,
    PILLAR3_DASFN_REVISION_HISTORY_UNPROVEN,
    PILLAR3_DASFN_STRUCTURED_COVERAGE_GAP,
    audit_bcb_pillar3_dasfn_pit_source,
    official_structured_coverage_contract,
)

CATALOG_URL = (
    "https://olinda.bcb.gov.br/olinda/servico/"
    "DASFN/versao/v1/odata/Recursos"
)
V1_DATASET_URL = "https://dadosabertos.bcb.gov.br/dataset/pilar3"
V2_DATASET_URL = "https://dadosabertos.bcb.gov.br/dataset/pilar3-v2"


def _catalog_payload(
    version: str,
    resource: str,
    *,
    extra_field: str | None = None,
) -> bytes:
    row: dict[str, object] = {
        "Api": "pilar3",
        "Versao": version,
        "Recurso": resource,
        "Url": "https://example.invalid/pillar3/resource",
    }
    if extra_field:
        row[extra_field] = "2026-09-04"
    return json.dumps({"value": [row]}).encode()


def _audit(*, v1_extra_field: str | None = None):
    return audit_bcb_pillar3_dasfn_pit_source(
        catalog_payloads=(
            (
                "v1",
                _catalog_payload(
                    "1.2.0",
                    "/km1/{semestre}",
                    extra_field=v1_extra_field,
                ),
            ),
            ("v2", _catalog_payload("2.0.0", "/km1/v2/{trimestre}")),
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


def test_audit_separates_structured_reference_dates_from_pit_vintages() -> None:
    audit = _audit()

    assert audit.structured_reference_date_coverage_proven
    assert audit.catalog_links_collected_daily_by_bcb
    assert audit.current_catalog_observation_point_in_time_from_collection
    assert not audit.institution_payloads_sampled
    assert not audit.payload_publication_timestamp_proven
    assert not audit.revision_history_proven
    assert not audit.historical_vintage_query_proven
    assert not audit.historical_replay_ready
    assert not audit.bank_evidence_point_in_time_ready
    assert not audit.readiness_promotion_allowed
    assert BANK_EVIDENCE_NOT_POINT_IN_TIME in audit.blockers
    assert PILLAR3_DASFN_REVISION_HISTORY_UNPROVEN in audit.blockers
    assert PILLAR3_DASFN_HISTORICAL_VINTAGE_QUERY_UNPROVEN in audit.blockers
    assert PILLAR3_DASFN_PAYLOAD_PUBLICATION_TIMESTAMP_UNPROVEN in audit.blockers
    assert PILLAR3_DASFN_STRUCTURED_COVERAGE_GAP in audit.blockers


def test_reference_period_templates_are_not_treated_as_vintage_selectors() -> None:
    audit = _audit()
    samples = {item.version_family: item for item in audit.observed_catalog_samples}

    assert samples["v1"].reference_selector_tokens == ("semestre",)
    assert samples["v2"].reference_selector_tokens == ("trimestre",)
    assert not audit.historical_vintage_query_proven


def test_revision_like_catalog_field_does_not_promote_payload_history() -> None:
    audit = _audit(v1_extra_field="DataUltimaAtualizacao")

    assert "DataUltimaAtualizacao" in audit.revision_like_catalog_fields
    assert not audit.payload_publication_timestamp_proven
    assert not audit.revision_history_proven
    assert not audit.bank_evidence_point_in_time_ready


def test_audit_preserves_live_catalog_provenance_for_both_versions() -> None:
    audit = _audit()

    assert len(audit.observed_catalog_samples) == 2
    assert all(item.row_count == 1 for item in audit.observed_catalog_samples)
    assert all(len(item.sha256) == 64 for item in audit.observed_catalog_samples)
    assert {item.version_family for item in audit.observed_catalog_samples} == {
        "v1",
        "v2",
    }


def test_missing_version_family_and_wrong_api_fail_closed() -> None:
    with pytest.raises(ValueError, match="missing DASFN catalog samples"):
        audit_bcb_pillar3_dasfn_pit_source(
            catalog_payloads=(("v1", _catalog_payload("1.2.0", "/km1/{semestre}")),),
            collected_at=datetime(2026, 9, 4, tzinfo=UTC),
            catalog_source_url=CATALOG_URL,
            v1_dataset_url=V1_DATASET_URL,
            v2_dataset_url=V2_DATASET_URL,
        )

    wrong_api = json.dumps(
        {
            "value": [
                {
                    "Api": "taxas_cartoes",
                    "Versao": "2.0.0",
                    "Recurso": "/km1/v2/{trimestre}",
                }
            ]
        }
    ).encode()
    with pytest.raises(ValueError, match="not scoped to the pilar3 API"):
        audit_bcb_pillar3_dasfn_pit_source(
            catalog_payloads=(
                ("v1", _catalog_payload("1.2.0", "/km1/{semestre}")),
                ("v2", wrong_api),
            ),
            collected_at=datetime(2026, 9, 4, tzinfo=UTC),
            catalog_source_url=CATALOG_URL,
            v1_dataset_url=V1_DATASET_URL,
            v2_dataset_url=V2_DATASET_URL,
        )


def test_invalid_odata_shape_and_naive_collection_time_are_rejected() -> None:
    invalid = json.dumps({"value": {}}).encode()
    with pytest.raises(TypeError, match="OData value list"):
        audit_bcb_pillar3_dasfn_pit_source(
            catalog_payloads=(
                ("v1", invalid),
                ("v2", _catalog_payload("2.0.0", "/km1/v2/{trimestre}")),
            ),
            collected_at=datetime(2026, 9, 4, tzinfo=UTC),
            catalog_source_url=CATALOG_URL,
            v1_dataset_url=V1_DATASET_URL,
            v2_dataset_url=V2_DATASET_URL,
        )

    with pytest.raises(ValueError, match="timezone-aware"):
        audit_bcb_pillar3_dasfn_pit_source(
            catalog_payloads=(
                ("v1", _catalog_payload("1.2.0", "/km1/{semestre}")),
                ("v2", _catalog_payload("2.0.0", "/km1/v2/{trimestre}")),
            ),
            collected_at=datetime(2026, 9, 4),
            catalog_source_url=CATALOG_URL,
            v1_dataset_url=V1_DATASET_URL,
            v2_dataset_url=V2_DATASET_URL,
        )


def test_report_serialization_keeps_fail_closed_boundary() -> None:
    payload = _audit().to_dict()

    assert payload["collected_at"] == "2026-09-04T00:00:00+00:00"
    assert payload["structured_coverage"]["v1_max_reference_date"] == "2023-06-30"
    assert payload["structured_coverage"]["v2_min_reference_date"] == "2025-12-31"
    assert payload["institution_payloads_sampled"] is False
    assert payload["bank_evidence_point_in_time_ready"] is False
