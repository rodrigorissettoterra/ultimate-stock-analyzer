from __future__ import annotations

from datetime import UTC, datetime
from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile

import pandas as pd
import pytest

from ultimate_stock_analyzer.collectors.cvm_targeted_statements import (
    load_company_statements_from_archive,
)


def _archive(*, ambiguous_fige: bool = False) -> bytes:
    metadata_rows = [
        {
            "CD_CVM": 6041,
            "DT_REFER": "2021-12-31",
            "VERSAO": 1,
            "ID_DOC": 100,
            "DT_RECEB": "2022-03-01T12:00:00",
        },
        {
            "CD_CVM": 24600,
            "DT_REFER": "2021-12-31",
            "VERSAO": 1,
            "ID_DOC": 200,
            "DT_RECEB": "2022-03-02T12:00:00",
        },
        {
            "CD_CVM": 24600,
            "DT_REFER": "2021-12-31",
            "VERSAO": 1,
            "ID_DOC": 201,
            "DT_RECEB": "2022-03-03T12:00:00",
        },
    ]
    if ambiguous_fige:
        metadata_rows.append(
            {
                "CD_CVM": 6041,
                "DT_REFER": "2021-12-31",
                "VERSAO": 1,
                "ID_DOC": 101,
                "DT_RECEB": "2022-03-04T12:00:00",
            }
        )

    statement_rows = [
        {
            "CD_CVM": 6041,
            "CNPJ_CIA": "01.548.981/0001-79",
            "DENOM_CIA": "INVESTIMENTOS BEMGE S.A.",
            "DT_REFER": "2021-12-31",
            "VERSAO": 1,
            "GRUPO_DFP": "DF Individual - Balanço Patrimonial Passivo",
            "DT_INI_EXERC": "2021-01-01",
            "DT_FIM_EXERC": "2021-12-31",
            "ORDEM_EXERC": "ÚLTIMO",
            "CD_CONTA": "2.07",
            "DS_CONTA": "Patrimônio Líquido",
            "VL_CONTA": 100.0,
            "ESCALA_MOEDA": "MIL",
        },
        {
            "CD_CVM": 24600,
            "CNPJ_CIA": "00.000.000/0000-00",
            "DENOM_CIA": "UNRELATED S.A.",
            "DT_REFER": "2021-12-31",
            "VERSAO": 1,
            "GRUPO_DFP": "DF Individual - Balanço Patrimonial Passivo",
            "DT_INI_EXERC": "2021-01-01",
            "DT_FIM_EXERC": "2021-12-31",
            "ORDEM_EXERC": "ÚLTIMO",
            "CD_CONTA": "2.07",
            "DS_CONTA": "Patrimônio Líquido",
            "VL_CONTA": 200.0,
            "ESCALA_MOEDA": "MIL",
        },
    ]

    buffer = BytesIO()
    with ZipFile(buffer, "w", ZIP_DEFLATED) as archive:
        archive.writestr(
            "dfp_cia_aberta_2021.csv",
            _csv_bytes(pd.DataFrame(metadata_rows)),
        )
        archive.writestr(
            "dfp_cia_aberta_BPP_ind_2021.csv",
            _csv_bytes(pd.DataFrame(statement_rows)),
        )
    return buffer.getvalue()


def _csv_bytes(frame: pd.DataFrame) -> bytes:
    return frame.to_csv(index=False, sep=";").encode("latin1")


def test_targeted_statement_loader_ignores_unrelated_metadata_ambiguity() -> None:
    lines = load_company_statements_from_archive(
        _archive(),
        cvm_code=6041,
        document_type="DFP",
        statements=("BPP",),
        scope_token="ind",
        collected_at=datetime(2026, 9, 1, tzinfo=UTC),
    )

    assert len(lines) == 1
    line = lines[0]
    assert line.company_id == "cvm:6041"
    assert line.account_code == "2.07"
    assert line.value_brl == pytest.approx(100_000.0)
    assert line.document_id == 100


def test_targeted_statement_loader_fails_closed_on_target_metadata_ambiguity() -> None:
    with pytest.raises(ValueError, match="ambiguous CVM filing metadata"):
        load_company_statements_from_archive(
            _archive(ambiguous_fige=True),
            cvm_code=6041,
            document_type="DFP",
            statements=("BPP",),
            scope_token="ind",
            collected_at=datetime(2026, 9, 1, tzinfo=UTC),
        )
