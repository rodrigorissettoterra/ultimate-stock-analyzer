from datetime import UTC, datetime

import pandas as pd

from ultimate_stock_analyzer.normalization.cvm import normalize_fca_securities


def test_fca_security_normalization_keeps_ticker_as_instrument_attribute() -> None:
    frame = pd.DataFrame(
        [
            {
                "CD_CVM": 12345,
                "CODIGO_NEGOCIACAO": "abcd3",
                "ISIN": "BRABCDACNOR1",
                "TP_VALOR_MOBILIARIO": "Ação Ordinária",
                "DS_MERCADO": "Bolsa",
                "DT_REFER": "2026-04-30",
                "VERSAO": 4,
                "DT_RECEB": "2026-05-05 10:00:00",
            },
            {
                "CD_CVM": 12345,
                "CODIGO_NEGOCIACAO": "abcd4",
                "ISIN": "BRABCDACNPR8",
                "TP_VALOR_MOBILIARIO": "Ação Preferencial",
                "DS_MERCADO": "Bolsa",
                "DT_REFER": "2026-04-30",
                "VERSAO": 4,
                "DT_RECEB": "2026-05-05 10:00:00",
            },
        ]
    )

    securities = normalize_fca_securities(
        frame,
        collected_at=datetime(2026, 8, 28, tzinfo=UTC),
        source_document="fca_cia_aberta_valor_mobiliario_2026.csv",
    )

    assert [item.ticker for item in securities] == ["ABCD3", "ABCD4"]
    assert {item.company_id for item in securities} == {"cvm:12345"}
