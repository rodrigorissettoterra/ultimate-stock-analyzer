from __future__ import annotations

from datetime import UTC, datetime

import pandas as pd
import pytest

from ultimate_stock_analyzer.orchestration.cvm_ingestion import CVMIngestionService


class _FakeCollector:
    def __init__(self, statement_frame: pd.DataFrame, metadata_frame: pd.DataFrame) -> None:
        self.statement_frame = statement_frame
        self.metadata_frame = metadata_frame

    def list_csv_files(self, _archive: bytes) -> list[str]:
        return [
            "dfp_cia_aberta_2024.csv",
            "dfp_cia_aberta_DRE_con_2024.csv",
        ]

    def find_csv(self, _archive: bytes, *_tokens: str) -> str:
        return "dfp_cia_aberta_DRE_con_2024.csv"

    def read_csv(self, _archive: bytes, filename: str) -> pd.DataFrame:
        if filename == "dfp_cia_aberta_2024.csv":
            return self.metadata_frame.copy()
        return self.statement_frame.copy()


def _statement_row(cvm_code: int) -> dict[str, object]:
    return {
        "CD_CVM": cvm_code,
        "CNPJ_CIA": "60.872.504/0001-23",
        "DENOM_CIA": "ITAU UNIBANCO HOLDING S.A.",
        "DT_REFER": "2024-12-31",
        "DT_INI_EXERC": "2024-01-01",
        "DT_FIM_EXERC": "2024-12-31",
        "ORDEM_EXERC": "ÚLTIMO",
        "CD_CONTA": "3.09",
        "DS_CONTA": "Lucro/Prejuízo Consolidado do Período",
        "VL_CONTA": 42128000.0,
        "ESCALA_MOEDA": "MIL",
        "VERSAO": 1,
        "GRUPO_DFP": "DF Consolidado - Demonstração do Resultado",
    }


def _metadata_row(
    cvm_code: int,
    *,
    document_id: int,
    received: str,
) -> dict[str, object]:
    return {
        "CD_CVM": cvm_code,
        "DT_REFER": "2024-12-31",
        "VERSAO": 1,
        "ID_DOC": document_id,
        "DT_RECEB": received,
        "LINK_DOC": f"https://example.invalid/{document_id}",
    }


def _service(
    statement_rows: list[dict[str, object]],
    metadata_rows: list[dict[str, object]],
) -> CVMIngestionService:
    collector = _FakeCollector(
        pd.DataFrame(statement_rows),
        pd.DataFrame(metadata_rows),
    )
    return CVMIngestionService(collector=collector)


def test_company_loader_ignores_unrelated_issuer_metadata_ambiguity() -> None:
    service = _service(
        [_statement_row(19348), _statement_row(24600)],
        [
            _metadata_row(19348, document_id=100, received="2025-02-05"),
            _metadata_row(24600, document_id=200, received="2025-03-01"),
            _metadata_row(24600, document_id=201, received="2025-03-02"),
        ],
    )

    lines = service.load_company_statements_from_archive(
        b"archive",
        cvm_code=19348,
        document_type="DFP",
        statements=("DRE",),
        scope_token="con",
        collected_at=datetime(2025, 4, 1, tzinfo=UTC),
    )

    assert len(lines) == 1
    assert lines[0].cvm_code == 19348
    assert lines[0].document_id == 100
    assert lines[0].available_from == datetime(2025, 2, 5, tzinfo=UTC)


def test_company_loader_rejects_target_natural_key_ambiguity() -> None:
    service = _service(
        [_statement_row(19348)],
        [
            _metadata_row(19348, document_id=100, received="2025-02-05"),
            _metadata_row(19348, document_id=101, received="2025-02-05"),
        ],
    )

    with pytest.raises(ValueError, match="ambiguous CVM filing metadata"):
        service.load_company_statements_from_archive(
            b"archive",
            cvm_code=19348,
            document_type="DFP",
            statements=("DRE",),
            scope_token="con",
            collected_at=datetime(2025, 4, 1, tzinfo=UTC),
        )


def test_company_loader_filters_statement_rows_before_normalization() -> None:
    service = _service(
        [_statement_row(19348), _statement_row(24600)],
        [_metadata_row(19348, document_id=100, received="2025-02-05")],
    )

    lines = service.load_company_statements_from_archive(
        b"archive",
        cvm_code=19348,
        document_type="DFP",
        statements=("DRE",),
        scope_token="con",
        collected_at=datetime(2025, 4, 1, tzinfo=UTC),
    )

    assert {line.cvm_code for line in lines} == {19348}


def test_company_loader_rejects_statement_member_without_cvm_identity() -> None:
    statement = pd.DataFrame([_statement_row(19348)]).drop(columns=["CD_CVM"])
    collector = _FakeCollector(
        statement,
        pd.DataFrame([_metadata_row(19348, document_id=100, received="2025-02-05")]),
    )
    service = CVMIngestionService(collector=collector)

    with pytest.raises(ValueError, match="has no CD_CVM column"):
        service.load_company_statements_from_archive(
            b"archive",
            cvm_code=19348,
            document_type="DFP",
            statements=("DRE",),
            scope_token="con",
            collected_at=datetime(2025, 4, 1, tzinfo=UTC),
        )
