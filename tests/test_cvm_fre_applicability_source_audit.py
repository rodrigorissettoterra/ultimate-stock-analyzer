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
SOURCE = (
    "https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/FRE/DADOS/"
    "fre_cia_aberta_2025.zip"
)


def _archive(*members: tuple[str, str]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, content in members:
            archive.writestr(name, content.encode("latin-1"))
    return buffer.getvalue()


def test_fre_detail_rows_are_joined_by_cnpj_or_document_identity() -> None:
    content = _archive(
        (
            "fre_cia_aberta_2025.csv",
            (
                "CD_CVM;CNPJ_CIA;ID_DOC;DT_RECEB;DT_REFER;VERSAO;DENOM_CIA\n"
                "9512;33000167000101;100;2025-05-01;2024-12-31;1;PETROBRAS\n"
                "19348;60701190000104;200;2025-05-02;2024-12-31;2;ITAU\n"
            ),
        ),
        (
            "fre_cia_atividade_cnpj_2025.csv",
            (
                "CNPJ_Companhia;DS_ATIVIDADE\n"
                "33000167000101;Exploracao e producao de petroleo\n"
            ),
        ),
        (
            "fre_cia_atividade_doc_2025.csv",
            "ID_Documento;CNAE\n200;6410\n",
        ),
    )
    report = audit_fre_historical_applicability_source(
        archive_content=content,
        collected_at=NOW,
        delivery_year=2025,
        source_url=SOURCE,
        requested_cvm_codes=[9512, 19348],
    )

    assert report.issuer_coverage_complete
    assert report.structured_activity_fields_found
    assert report.filing_timing_fields_found
    assert {item.column_name for item in report.activity_candidate_fields} == {
        "CNAE",
        "DS_ATIVIDADE",
    }
    assert "DT_RECEB" in {item.column_name for item in report.timing_candidate_fields}
    assert "DT_REFER" not in {item.column_name for item in report.timing_candidate_fields}
    assert "DT_REFER" in {item.column_name for item in report.reference_candidate_fields}
    assert FRE_ACTIVITY_TO_MODEL_MAPPING_UNPROVEN in report.blockers
    assert HISTORICAL_MODEL_APPLICABILITY_UNPROVEN in report.blockers
    assert not report.readiness_promotion_allowed


def test_reference_period_alone_does_not_prove_filing_timing() -> None:
    content = _archive(
        (
            "fre_cia_aberta_2025.csv",
            "CD_CVM;CNPJ_CIA;ID_DOC;DT_REFER;VERSAO\n19348;60701190000104;200;2024-12-31;2\n",
        ),
        (
            "fre_cia_atividade_2025.csv",
            "ID_Documento;DS_ATIVIDADE\n200;Atividade bancaria\n",
        ),
    )
    report = audit_fre_historical_applicability_source(
        archive_content=content,
        collected_at=NOW,
        delivery_year=2025,
        source_url=SOURCE,
        requested_cvm_codes=[19348],
    )
    assert report.reference_metadata_fields_found
    assert not report.filing_timing_fields_found
    assert FRE_FILING_TIMING_FIELDS_UNPROVEN in report.blockers


def test_revision_metadata_alone_does_not_prove_filing_timing() -> None:
    content = _archive(
        (
            "fre_cia_aberta_2025.csv",
            "CD_CVM;CNPJ_CIA;ID_DOC;VERSAO\n19348;60701190000104;200;2\n",
        ),
        (
            "fre_cia_atividade_2025.csv",
            "ID_Documento;DS_ATIVIDADE\n200;Atividade bancaria\n",
        ),
    )
    report = audit_fre_historical_applicability_source(
        archive_content=content,
        collected_at=NOW,
        delivery_year=2025,
        source_url=SOURCE,
        requested_cvm_codes=[19348],
    )
    assert report.revision_metadata_fields_found
    assert not report.filing_timing_fields_found
    assert FRE_FILING_TIMING_FIELDS_UNPROVEN in report.blockers


def test_fre_audit_fails_closed_when_activity_field_is_missing() -> None:
    content = _archive(
        (
            "fre_cia_aberta_2025.csv",
            "CD_CVM;CNPJ_CIA;ID_DOC;DT_RECEB;VERSAO\n19348;60701190000104;200;2025-05-02;2\n",
        )
    )
    report = audit_fre_historical_applicability_source(
        archive_content=content,
        collected_at=NOW,
        delivery_year=2025,
        source_url=SOURCE,
        requested_cvm_codes=[19348],
    )
    assert report.issuer_coverage_complete
    assert not report.structured_activity_fields_found
    assert FRE_STRUCTURED_ACTIVITY_FIELD_UNAVAILABLE in report.blockers


def test_fre_audit_reports_missing_requested_issuer() -> None:
    content = _archive(
        (
            "fre_cia_aberta_2025.csv",
            "CD_CVM;CNPJ_CIA;ID_DOC;DT_RECEB;VERSAO\n9512;33000167000101;100;2025-05-01;1\n",
        )
    )
    report = audit_fre_historical_applicability_source(
        archive_content=content,
        collected_at=NOW,
        delivery_year=2025,
        source_url=SOURCE,
        requested_cvm_codes=[9512, 19348],
    )
    assert report.issuer_codes_observed == (9512,)
    assert not report.issuer_coverage_complete
    assert FRE_ISSUER_COVERAGE_INCOMPLETE in report.blockers
