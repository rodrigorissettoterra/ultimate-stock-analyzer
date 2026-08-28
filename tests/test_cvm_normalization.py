from datetime import UTC, datetime

import pandas as pd

from ultimate_stock_analyzer.normalization.cvm import (
    attach_document_metadata,
    normalize_issuer_registry,
    normalize_statement,
    point_in_time_lines,
)


def test_normalize_active_issuers_uses_stable_cvm_identity() -> None:
    frame = pd.DataFrame(
        [
            {
                "CD_CVM": 12345,
                "CNPJ_CIA": "00.000.000/0001-00",
                "DENOM_SOCIAL": "COMPANHIA TESTE S.A.",
                "DENOM_COMERC": "TESTE",
                "SIT": "ATIVO",
                "DT_REG": "2020-01-02",
            },
            {
                "CD_CVM": 99999,
                "CNPJ_CIA": "99.999.999/0001-99",
                "DENOM_SOCIAL": "ANTIGA S.A.",
                "SIT": "CANCELADA",
            },
        ]
    )

    issuers = normalize_issuer_registry(
        frame,
        collected_at=datetime(2026, 8, 28, tzinfo=UTC),
    )

    assert len(issuers) == 1
    assert issuers[0].company_id == "cvm:12345"
    assert issuers[0].legal_name == "COMPANHIA TESTE S.A."


def test_statement_normalization_applies_scale_and_metadata() -> None:
    statement = pd.DataFrame(
        [
            {
                "CD_CVM": 12345,
                "CNPJ_CIA": "00.000.000/0001-00",
                "DENOM_CIA": "COMPANHIA TESTE S.A.",
                "DT_REFER": "2025-12-31",
                "VERSAO": 2,
                "ID_DOC": 77,
                "GRUPO_DFP": "DF Consolidado",
                "ORDEM_EXERC": "ÚLTIMO",
                "DT_INI_EXERC": "2025-01-01",
                "DT_FIM_EXERC": "2025-12-31",
                "CD_CONTA": "3.01",
                "DS_CONTA": "Receita",
                "VL_CONTA": 1250.5,
                "ESCALA_MOEDA": "MIL",
            }
        ]
    )
    metadata = pd.DataFrame([{"ID_DOC": 77, "DT_RECEB": "2026-02-20 18:30:00"}])
    joined = attach_document_metadata(statement, metadata)

    lines = normalize_statement(
        joined,
        document_type="DFP",
        statement="DRE",
        collected_at=datetime(2026, 8, 28, tzinfo=UTC),
        source_document="dfp_cia_aberta_DRE_con_2025.csv",
    )

    assert lines[0].value_brl == 1_250_500.0
    assert lines[0].available_from == datetime(2026, 2, 20, 18, 30, tzinfo=UTC)
    assert lines[0].version == 2


def test_point_in_time_keeps_latest_revision_available_at_cutoff() -> None:
    base = {
        "CD_CVM": 12345,
        "CNPJ_CIA": "00.000.000/0001-00",
        "DENOM_CIA": "COMPANHIA TESTE S.A.",
        "DT_REFER": "2025-12-31",
        "GRUPO_DFP": "DF Consolidado",
        "ORDEM_EXERC": "ÚLTIMO",
        "CD_CONTA": "3.01",
        "DS_CONTA": "Receita",
        "ESCALA_MOEDA": "UNIDADE",
    }
    frame = pd.DataFrame(
        [
            {**base, "VERSAO": 1, "ID_DOC": 10, "VL_CONTA": 100, "DT_RECEB": "2026-02-10"},
            {**base, "VERSAO": 2, "ID_DOC": 11, "VL_CONTA": 110, "DT_RECEB": "2026-03-10"},
        ]
    )
    lines = normalize_statement(
        frame,
        document_type="DFP",
        statement="DRE",
        collected_at=datetime(2026, 8, 28, tzinfo=UTC),
        source_document="fixture.csv",
    )

    february = point_in_time_lines(
        lines,
        as_of=datetime(2026, 2, 28, tzinfo=UTC),
    )
    april = point_in_time_lines(
        lines,
        as_of=datetime(2026, 4, 1, tzinfo=UTC),
    )

    assert february[0].value_brl == 100.0
    assert february[0].version == 1
    assert april[0].value_brl == 110.0
    assert april[0].version == 2
