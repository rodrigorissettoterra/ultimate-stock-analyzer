from __future__ import annotations

import io
import zipfile
from datetime import UTC, datetime

from ultimate_stock_analyzer.backtesting.cvm_fca_applicability_source_audit import (
    FCA_APPLICABILITY_FIELD_UNAVAILABLE,
    FCA_APPLICABILITY_TO_MODEL_MAPPING_UNPROVEN,
    FCA_FILING_TIMING_FIELDS_UNPROVEN,
    FCA_ISSUER_COVERAGE_INCOMPLETE,
    HISTORICAL_MODEL_APPLICABILITY_UNPROVEN,
    audit_fca_historical_applicability_source,
)

NOW = datetime(2026, 9, 3, tzinfo=UTC)
SOURCE = (
    "https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/FCA/DADOS/"
    "fca_cia_aberta_2025.zip"
)


def _archive(*members: tuple[str, str]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, content in members:
            archive.writestr(name, content.encode("latin-1"))
    return buffer.getvalue()


def test_fca_audit_joins_cnpj_and_separates_evidence_categories() -> None:
    content = _archive(
        (
            "fca_cia_aberta_2025.csv",
            (
                "CD_CVM;CNPJ_CIA;DT_RECEB;DT_REFER;VERSAO\n"
                "9512;33000167000101;2025-05-10;2024-12-31;1\n"
                "19348;60701190000104;2025-05-11;2024-12-31;2\n"
            ),
        ),
        (
            "fca_cia_aberta_geral_2025.csv",
            (
                "CNPJ_Companhia;SETOR_ATIVIDADE;CNAE\n"
                "33000167000101;Petroleo e Gas;0600\n"
                "60701190000104;Intermediacao Financeira;6410\n"
            ),
        ),
    )

    report = audit_fca_historical_applicability_source(
        archive_content=content,
        collected_at=NOW,
        delivery_year=2025,
        source_url=SOURCE,
        requested_cvm_codes=[9512, 19348],
    )

    assert report.issuer_coverage_complete
    assert report.issuer_codes_observed == (9512, 19348)
    assert report.applicability_fields_found
    assert report.filing_timing_fields_found
    assert report.reference_metadata_fields_found
    assert report.revision_metadata_fields_found
    assert {item.column_name for item in report.applicability_candidate_fields} == {
        "CNAE",
        "SETOR_ATIVIDADE",
    }
    assert "DT_RECEB" in {item.column_name for item in report.timing_candidate_fields}
    assert "DT_REFER" not in {item.column_name for item in report.timing_candidate_fields}
    assert "DT_REFER" in {item.column_name for item in report.reference_candidate_fields}
    assert not report.deterministic_model_routing_supported
    assert not report.sector_routing_point_in_time_ready
    assert not report.readiness_promotion_allowed
    assert FCA_APPLICABILITY_TO_MODEL_MAPPING_UNPROVEN in report.blockers
    assert HISTORICAL_MODEL_APPLICABILITY_UNPROVEN in report.blockers


def test_reference_period_alone_does_not_prove_fca_filing_timing() -> None:
    content = _archive(
        (
            "fca_cia_aberta_2025.csv",
            "CD_CVM;CNPJ_CIA;DT_REFER;VERSAO\n19348;60701190000104;2024-12-31;2\n",
        ),
        (
            "fca_cia_aberta_geral_2025.csv",
            "CNPJ_Companhia;SETOR_ATIVIDADE\n60701190000104;Intermediacao Financeira\n",
        ),
    )

    report = audit_fca_historical_applicability_source(
        archive_content=content,
        collected_at=NOW,
        delivery_year=2025,
        source_url=SOURCE,
        requested_cvm_codes=[19348],
    )

    assert report.reference_metadata_fields_found
    assert not report.filing_timing_fields_found
    assert FCA_FILING_TIMING_FIELDS_UNPROVEN in report.blockers


def test_fca_audit_fails_closed_without_applicability_field() -> None:
    content = _archive(
        (
            "fca_cia_aberta_2025.csv",
            "CD_CVM;CNPJ_CIA;DT_RECEB;VERSAO\n19348;60701190000104;2025-05-11;2\n",
        ),
        (
            "fca_cia_aberta_endereco_2025.csv",
            "CNPJ_Companhia;MUNICIPIO\n60701190000104;SAO PAULO\n",
        ),
    )

    report = audit_fca_historical_applicability_source(
        archive_content=content,
        collected_at=NOW,
        delivery_year=2025,
        source_url=SOURCE,
        requested_cvm_codes=[19348],
    )

    assert report.issuer_coverage_complete
    assert not report.applicability_fields_found
    assert FCA_APPLICABILITY_FIELD_UNAVAILABLE in report.blockers
    assert not report.sector_routing_point_in_time_ready


def test_fca_audit_reports_missing_requested_issuer() -> None:
    content = _archive(
        (
            "fca_cia_aberta_2025.csv",
            "CD_CVM;CNPJ_CIA;DT_RECEB;VERSAO\n9512;33000167000101;2025-05-10;1\n",
        ),
        (
            "fca_cia_aberta_geral_2025.csv",
            "CNPJ_Companhia;SETOR_ATIVIDADE\n33000167000101;Petroleo e Gas\n",
        ),
    )

    report = audit_fca_historical_applicability_source(
        archive_content=content,
        collected_at=NOW,
        delivery_year=2025,
        source_url=SOURCE,
        requested_cvm_codes=[9512, 19348],
    )

    assert report.issuer_codes_observed == (9512,)
    assert not report.issuer_coverage_complete
    assert FCA_ISSUER_COVERAGE_INCOMPLETE in report.blockers
