from __future__ import annotations

import json
from datetime import UTC, date, datetime

import pytest

from ultimate_stock_analyzer.backtesting.bcb_ifdata_pit_source_audit import (
    BANK_EVIDENCE_NOT_POINT_IN_TIME,
    IFDATA_HISTORICAL_VINTAGE_QUERY_UNAVAILABLE,
    IFDATA_REVISION_HISTORY_UNAVAILABLE,
    IFDATA_ROW_PUBLICATION_TIMESTAMP_UNAVAILABLE,
    audit_bcb_ifdata_pit_source,
    contractual_initial_release_evidence,
)


def _metadata(*, extra_property: str | None = None) -> bytes:
    extra = (
        f'<Property Name="{extra_property}" Type="Edm.String" />'
        if extra_property
        else ""
    )
    return (
        '<?xml version="1.0" encoding="utf-8"?>'
        '<edmx:Edmx xmlns:edmx="http://docs.oasis-open.org/odata/ns/edmx" '
        'Version="4.0"><edmx:DataServices>'
        '<Schema xmlns="http://docs.oasis-open.org/odata/ns/edm" Namespace="IFDATA">'
        '<EntityType Name="IfDataValor">'
        '<Property Name="AnoMes" Type="Edm.Int32" />'
        '<Property Name="CodInst" Type="Edm.String" />'
        f"{extra}"
        "</EntityType>"
        '<Function Name="IfDataValores">'
        '<Parameter Name="AnoMes" Type="Edm.Int32" />'
        '<Parameter Name="TipoInstituicao" Type="Edm.Int32" />'
        '<Parameter Name="Relatorio" Type="Edm.String" />'
        "</Function>"
        "</Schema></edmx:DataServices></edmx:Edmx>"
    ).encode()


def _sample(ano_mes: int, *, kind: str = "report_1") -> tuple[int, str, bytes]:
    content = json.dumps(
        {
            "value": [
                {
                    "AnoMes": ano_mes,
                    "CodInst": "C0080099",
                    "Conta": "78182",
                    "Saldo": 1.0,
                }
            ]
        }
    ).encode()
    return ano_mes, kind, content


def _audit(metadata_content: bytes | None = None):
    periods = (202412, 202506, 202512)
    return audit_bcb_ifdata_pit_source(
        metadata_content=metadata_content or _metadata(),
        sample_payloads=tuple(_sample(period) for period in periods),
        requested_ano_mes=periods,
        collected_at=datetime(2026, 9, 2, tzinfo=UTC),
        source_dataset_url=(
            "https://dadosabertos.bcb.gov.br/dataset/"
            "ifdata---dados-selecionados-de-instituies-financeiras"
        ),
    )


def test_contractual_initial_release_uses_official_60_and_90_day_delays() -> None:
    december = contractual_initial_release_evidence(202412)
    june = contractual_initial_release_evidence(202506)

    assert december.reference_date == date(2024, 12, 31)
    assert december.publication_delay_days == 90
    assert december.contractual_initial_release_date == date(2025, 3, 31)
    assert june.reference_date == date(2025, 6, 30)
    assert june.publication_delay_days == 60
    assert june.contractual_initial_release_date == date(2025, 8, 29)


def test_audit_separates_initial_release_timing_from_revision_aware_replay() -> None:
    audit = _audit()

    assert audit.initial_publication_timing_proven
    assert audit.current_observation_point_in_time_from_collection
    assert not audit.row_level_publication_timestamp_proven
    assert not audit.revision_history_proven
    assert not audit.historical_vintage_query_proven
    assert not audit.historical_replay_ready
    assert not audit.bank_evidence_point_in_time_ready
    assert not audit.readiness_promotion_allowed
    assert BANK_EVIDENCE_NOT_POINT_IN_TIME in audit.blockers
    assert IFDATA_REVISION_HISTORY_UNAVAILABLE in audit.blockers
    assert IFDATA_HISTORICAL_VINTAGE_QUERY_UNAVAILABLE in audit.blockers
    assert IFDATA_ROW_PUBLICATION_TIMESTAMP_UNAVAILABLE in audit.blockers


def test_revision_like_field_name_is_not_promoted_without_semantic_contract() -> None:
    audit = _audit(_metadata(extra_property="DataAtualizacao"))

    assert audit.revision_like_metadata_names == ("DataAtualizacao",)
    assert not audit.revision_history_proven
    assert not audit.bank_evidence_point_in_time_ready


def test_audit_preserves_metadata_and_live_sample_provenance() -> None:
    audit = _audit()

    assert len(audit.metadata_sha256) == 64
    assert audit.metadata_size_bytes > 0
    assert "AnoMes" in audit.metadata_property_names
    assert {"AnoMes", "Relatorio", "TipoInstituicao"}.issubset(
        audit.metadata_parameter_names
    )
    assert len(audit.observed_samples) == 3
    assert all(len(sample.sha256) == 64 for sample in audit.observed_samples)
    assert all(sample.row_count == 1 for sample in audit.observed_samples)


def test_invalid_reference_period_and_incomplete_samples_fail_closed() -> None:
    with pytest.raises(ValueError, match="quarterly reference periods"):
        contractual_initial_release_evidence(202505)

    with pytest.raises(ValueError, match="missing IFData live samples"):
        audit_bcb_ifdata_pit_source(
            metadata_content=_metadata(),
            sample_payloads=(_sample(202412),),
            requested_ano_mes=(202412, 202512),
            collected_at=datetime(2026, 9, 2, tzinfo=UTC),
            source_dataset_url=(
                "https://dadosabertos.bcb.gov.br/dataset/"
                "ifdata---dados-selecionados-de-instituies-financeiras"
            ),
        )


def test_report_serialization_keeps_fail_closed_boundary() -> None:
    payload = _audit().to_dict()

    assert payload["collected_at"] == "2026-09-02T00:00:00+00:00"
    assert payload["initial_release_evidence"][0][
        "contractual_initial_release_date"
    ] == "2025-03-31"
    assert payload["observed_samples"][0]["observed_fields"]
    assert payload["bank_evidence_point_in_time_ready"] is False
