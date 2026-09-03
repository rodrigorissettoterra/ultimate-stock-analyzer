from __future__ import annotations

import io
import zipfile
from datetime import UTC, datetime

from ultimate_stock_analyzer.backtesting.cvm_fca_applicability_filing_ledger import (
    FCA_APPLICABILITY_DETAIL_NOT_FOUND,
    FCA_APPLICABILITY_ISSUER_IDENTITY_MISMATCH,
    FCA_APPLICABILITY_RECEIPT_DATE_MISSING,
    FCA_APPLICABILITY_REFERENCE_DATE_MISMATCH,
    FCA_APPLICABILITY_ROOT_JOIN_AMBIGUOUS,
    FCA_APPLICABILITY_VERSION_MISMATCH,
    build_fca_applicability_filing_ledger,
)

NOW = datetime(2026, 9, 3, tzinfo=UTC)
SOURCE = (
    "https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/FCA/DADOS/"
    "fca_cia_aberta_2025.zip"
)


def _archive(root: str, detail: str) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("fca_cia_aberta_2025.csv", root.encode("latin-1"))
        archive.writestr("fca_cia_aberta_geral_2025.csv", detail.encode("latin-1"))
    return buffer.getvalue()


def _root(*rows: str) -> str:
    return (
        "CNPJ_CIA;DT_REFER;VERSAO;DENOM_CIA;CD_CVM;CATEG_DOC;ID_DOC;DT_RECEB;LINK_DOC\n"
        + "".join(rows)
    )


def _detail(*rows: str) -> str:
    return (
        "CNPJ_Companhia;Data_Referencia;Versao;ID_Documento;Nome_Empresarial;"
        "Codigo_CVM;Setor_Atividade;Descricao_Atividade\n"
        + "".join(rows)
    )


def test_exact_same_issuer_period_join_materializes_conservative_availability() -> None:
    content = _archive(
        _root(
            "60701190000104;2025-01-01;2;ITAU UNIBANCO;19348;FCA;42;2025-05-15;doc\n"
        ),
        _detail(
            "60701190000104;2025-01-01;2;42;ITAU UNIBANCO;19348;Bancos;"
            "Atividade bancaria\n"
        ),
    )
    ledger = build_fca_applicability_filing_ledger(
        archive_content=content,
        collected_at=NOW,
        delivery_year=2025,
        source_url=SOURCE,
        requested_cvm_codes=[19348],
    )

    assert ledger.blockers == ()
    assert ledger.applicability_detail_codes_observed == (19348,)
    assert ledger.missing_applicability_detail_codes == ()
    assert len(ledger.filings) == 1
    filing = ledger.filings[0]
    assert filing.document_id == 42
    assert filing.version == 2
    assert filing.sector_activity == "Bancos"
    assert filing.available_from == datetime(2025, 5, 16, tzinfo=UTC)
    assert filing.issuer_identity_match
    assert filing.reference_date_match
    assert len(filing.evidence_sha256) == 64


def test_cross_issuer_document_join_fails_closed() -> None:
    content = _archive(
        _root(
            "33000167000101;2025-01-01;1;PETROBRAS;9512;FCA;42;2025-05-15;doc\n"
        ),
        _detail(
            "60701190000104;2025-01-01;1;42;ITAU UNIBANCO;19348;Bancos;"
            "Atividade bancaria\n"
        ),
    )
    ledger = build_fca_applicability_filing_ledger(
        archive_content=content,
        collected_at=NOW,
        delivery_year=2025,
        source_url=SOURCE,
        requested_cvm_codes=[9512, 19348],
    )
    assert ledger.filings == ()
    assert FCA_APPLICABILITY_ISSUER_IDENTITY_MISMATCH in ledger.blockers
    assert ledger.applicability_detail_codes_observed == (19348,)
    assert ledger.missing_applicability_detail_codes == (9512,)
    assert FCA_APPLICABILITY_DETAIL_NOT_FOUND in ledger.blockers


def test_reference_date_mismatch_fails_closed() -> None:
    content = _archive(
        _root("60701190000104;2025-01-01;2;ITAU;19348;FCA;42;2025-05-15;doc\n"),
        _detail(
            "60701190000104;2024-01-01;2;42;ITAU;19348;Bancos;Atividade bancaria\n"
        ),
    )
    ledger = build_fca_applicability_filing_ledger(
        archive_content=content,
        collected_at=NOW,
        delivery_year=2025,
        source_url=SOURCE,
        requested_cvm_codes=[19348],
    )
    assert ledger.filings == ()
    assert FCA_APPLICABILITY_REFERENCE_DATE_MISMATCH in ledger.blockers


def test_missing_one_requested_detail_issuer_is_reported() -> None:
    content = _archive(
        _root(
            "60701190000104;2025-01-01;1;ITAU;19348;FCA;42;2025-05-15;doc-a\n",
            "33000167000101;2025-01-01;1;PETROBRAS;9512;FCA;43;2025-05-15;doc-b\n",
        ),
        _detail(
            "60701190000104;2025-01-01;1;42;ITAU;19348;Bancos;Atividade bancaria\n"
        ),
    )
    ledger = build_fca_applicability_filing_ledger(
        archive_content=content,
        collected_at=NOW,
        delivery_year=2025,
        source_url=SOURCE,
        requested_cvm_codes=[19348, 9512],
    )
    assert len(ledger.filings) == 1
    assert ledger.applicability_detail_codes_observed == (19348,)
    assert ledger.missing_applicability_detail_codes == (9512,)
    assert FCA_APPLICABILITY_DETAIL_NOT_FOUND in ledger.blockers


def test_version_mismatch_fails_closed() -> None:
    content = _archive(
        _root("60701190000104;2025-01-01;2;ITAU;19348;FCA;42;2025-05-15;doc\n"),
        _detail(
            "60701190000104;2025-01-01;3;42;ITAU;19348;Bancos;Atividade bancaria\n"
        ),
    )
    ledger = build_fca_applicability_filing_ledger(
        archive_content=content,
        collected_at=NOW,
        delivery_year=2025,
        source_url=SOURCE,
        requested_cvm_codes=[19348],
    )
    assert ledger.filings == ()
    assert FCA_APPLICABILITY_VERSION_MISMATCH in ledger.blockers


def test_missing_receipt_date_fails_closed() -> None:
    content = _archive(
        _root("60701190000104;2025-01-01;2;ITAU;19348;FCA;42;;doc\n"),
        _detail(
            "60701190000104;2025-01-01;2;42;ITAU;19348;Bancos;Atividade bancaria\n"
        ),
    )
    ledger = build_fca_applicability_filing_ledger(
        archive_content=content,
        collected_at=NOW,
        delivery_year=2025,
        source_url=SOURCE,
        requested_cvm_codes=[19348],
    )
    assert ledger.filings == ()
    assert FCA_APPLICABILITY_RECEIPT_DATE_MISSING in ledger.blockers


def test_duplicate_root_document_id_is_ambiguous() -> None:
    content = _archive(
        _root(
            "60701190000104;2025-01-01;2;ITAU;19348;FCA;42;2025-05-15;doc-a\n",
            "60701190000104;2025-01-01;2;ITAU;19348;FCA;42;2025-05-16;doc-b\n",
        ),
        _detail(
            "60701190000104;2025-01-01;2;42;ITAU;19348;Bancos;Atividade bancaria\n"
        ),
    )
    ledger = build_fca_applicability_filing_ledger(
        archive_content=content,
        collected_at=NOW,
        delivery_year=2025,
        source_url=SOURCE,
        requested_cvm_codes=[19348],
    )
    assert ledger.filings == ()
    assert FCA_APPLICABILITY_ROOT_JOIN_AMBIGUOUS in ledger.blockers
