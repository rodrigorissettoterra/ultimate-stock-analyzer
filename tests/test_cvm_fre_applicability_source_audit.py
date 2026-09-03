from __future__ import annotations

import io
import zipfile
from datetime import UTC, datetime

from ultimate_stock_analyzer.backtesting.cvm_fre_applicability_source_audit import (
    FRE_ACTIVITY_TO_MODEL_MAPPING_UNPROVEN,
    FRE_FILING_TIMING_FIELDS_UNPROVEN,
    FRE_ISSUER_COVERAGE_INCOMPLETE,
    FRE_STRUCTURED_ACTIVITY_FIELD_UNAVAILABLE,
    HISTORICAL_MODEL_APPLICABILITY_UNPROVEN,
    audit_fre_historical_applicability_source,
)

NOW = datetime(2026, 9, 3, tzinfo=UTC)


def _archive(*members: tuple[str, str]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, content in members:
            archive.writestr(name, content.encode("latin-1"))
    return buffer.getvalue()


def test_fre_audit_separates_filing_reference_and_revision_metadata() -> None:
    content = _archive(
        (
            "fre_cia_aberta.csv",
            (
                "CD_CVM;DT_RECEB;DT_REFER;VERSAO;DENOM_CIA\n"
                "9512;2025-05-01;2024-12-31;1;PETROBRAS\n"
                "4170;2025-05-02;2024-12-31;2;VALE\n"
            ),
        ),
        (
            "fre_cia_atividade.csv",
            (
                "CD_CVM;DS_ATIVIDADE;CNAE\n"
                "9512;Exploracao e producao de petroleo;0600\n"
                "4170;Extracao mineral;0710\n"
            ),
        ),
    )

    report = audit_fre_historical_applicability_source(
        archive_content=content,
        collected_at=NOW,
        delivery_year=2025,
        source_url=(
            "https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/FRE/DADOS/"
            "fre_cia_aberta_2025.zip"
        ),
        requested_cvm_codes=[9512, 4170],
    )

    assert report.issuer_coverage_complete
    assert report.structured_activity_fields_found
    assert report.filing_timing_fields_found
    assert report.reference_metadata_fields_found
    assert report.revision_metadata_fields_found
    assert {item.column_name for item in report.activity_candidate_fields} == {
        "DS_ATIVIDADE",
        "CNAE",
    }
    assert "DT_RECEB" in {
        item.column_name for item in report.timing_candidate_fields
    }
    assert "DT_REFER" not in {
        item.column_name for item in report.timing_candidate_fields
    }
    assert "DT_REFER" in {
        item.column_name for item in report.reference_candidate_fields
    }
    assert "VERSAO" not in {
        item.column_name for item in report.timing_candidate_fields
    }
    assert "VERSAO" in {
        item.column_name for item in report.revision_candidate_fields
    }
    assert not report.deterministic_model_routing_supported
    assert not report.sector_routing_point_in_time_ready
    assert not report.readiness_promotion_allowed
    assert FRE_ACTIVITY_TO_MODEL_MAPPING_UNPROVEN in report.blockers
    assert HISTORICAL_MODEL_APPLICABILITY_UNPROVEN in report.blockers


def test_reference_period_alone_does_not_prove_filing_timing() -> None:
    content = _archive(
        (
            "fre_cia_aberta.csv",
            (
                "CD_CVM;DT_REFER;VERSAO;DENOM_CIA\n"
                "19348;2024-12-31;3;ITAU UNIBANCO\n"
            ),
        ),
        (
            "fre_cia_atividade.csv",
            (
                "CD_CVM;DS_ATIVIDADE\n"
                "19348;Atividade bancaria\n"
            ),
        ),
    )

    report = audit_fre_historical_applicability_source(
        archive_content=content,
        collected_at=NOW,
        delivery_year=2025,
        source_url=(
            "https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/FRE/DADOS/"
            "fre_cia_aberta_2025.zip"
        ),
        requested_cvm_codes=[19348],
    )

    assert report.reference_metadata_fields_found
    assert report.revision_metadata_fields_found
    assert not report.filing_timing_fields_found
    assert FRE_FILING_TIMING_FIELDS_UNPROVEN in report.blockers
    assert not report.sector_routing_point_in_time_ready


def test_revision_metadata_alone_does_not_prove_filing_timing() -> None:
    content = _archive(
        (
            "fre_cia_aberta.csv",
            (
                "CD_CVM;VERSAO;DENOM_CIA\n"
                "19348;3;ITAU UNIBANCO\n"
            ),
        ),
        (
            "fre_cia_atividade.csv",
            (
                "CD_CVM;DS_ATIVIDADE\n"
                "19348;Atividade bancaria\n"
            ),
        ),
    )

    report = audit_fre_historical_applicability_source(
        archive_content=content,
        collected_at=NOW,
        delivery_year=2025,
        source_url=(
            "https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/FRE/DADOS/"
            "fre_cia_aberta_2025.zip"
        ),
        requested_cvm_codes=[19348],
    )

    assert report.revision_metadata_fields_found
    assert not report.filing_timing_fields_found
    assert FRE_FILING_TIMING_FIELDS_UNPROVEN in report.blockers
    assert not report.sector_routing_point_in_time_ready


def test_fre_audit_fails_closed_when_structured_activity_field_is_missing() -> None:
    content = _archive(
        (
            "fre_cia_aberta.csv",
            (
                "CD_CVM;DT_RECEB;VERSAO;DENOM_CIA\n"
                "19348;2025-05-01;1;ITAU UNIBANCO\n"
            ),
        )
    )

    report = audit_fre_historical_applicability_source(
        archive_content=content,
        collected_at=NOW,
        delivery_year=2025,
        source_url=(
            "https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/FRE/DADOS/"
            "fre_cia_aberta_2025.zip"
        ),
        requested_cvm_codes=[19348],
    )

    assert report.issuer_coverage_complete
    assert not report.structured_activity_fields_found
    assert FRE_STRUCTURED_ACTIVITY_FIELD_UNAVAILABLE in report.blockers
    assert not report.sector_routing_point_in_time_ready


def test_fre_audit_reports_missing_requested_issuer() -> None:
    content = _archive(
        (
            "fre_cia_aberta.csv",
            (
                "CD_CVM;DT_RECEB;VERSAO;DENOM_CIA\n"
                "9512;2025-05-01;1;PETROBRAS\n"
            ),
        ),
        (
            "fre_cia_atividade.csv",
            (
                "CD_CVM;DS_ATIVIDADE\n"
                "9512;Exploracao e producao de petroleo\n"
            ),
        ),
    )

    report = audit_fre_historical_applicability_source(
        archive_content=content,
        collected_at=NOW,
        delivery_year=2025,
        source_url=(
            "https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/FRE/DADOS/"
            "fre_cia_aberta_2025.zip"
        ),
        requested_cvm_codes=[9512, 4170],
    )

    assert report.issuer_codes_observed == (9512,)
    assert not report.issuer_coverage_complete
    assert FRE_ISSUER_COVERAGE_INCOMPLETE in report.blockers
