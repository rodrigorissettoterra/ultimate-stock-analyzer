from __future__ import annotations

from datetime import UTC, date, datetime

import pandas as pd
import pytest

from ultimate_stock_analyzer.orchestration.cvm_ingestion import CVMIngestionService


class LiveFCACollector:
    def read_registry_bytes(self, content: bytes) -> pd.DataFrame:
        assert content == b"registry"
        return pd.DataFrame(
            [
                {
                    "CD_CVM": 9512,
                    "CNPJ_CIA": "33.000.167/0001-01",
                    "DENOM_SOCIAL": "PETROLEO BRASILEIRO S.A. PETROBRAS",
                    "SIT": "ATIVO",
                }
            ]
        )

    def find_csv(self, archive: bytes, *tokens: str) -> str:
        assert archive == b"fca"
        assert tokens == ("valor_mobiliario",)
        return "fca_cia_aberta_valor_mobiliario_2025.csv"

    def list_csv_files(self, archive: bytes) -> list[str]:
        assert archive == b"fca"
        return ["fca_cia_aberta_valor_mobiliario_2025.csv"]

    def read_csv(self, archive: bytes, filename: str) -> pd.DataFrame:
        assert archive == b"fca"
        assert filename == "fca_cia_aberta_valor_mobiliario_2025.csv"
        return pd.DataFrame(
            [
                {
                    "CNPJ_Companhia": "33.000.167/0001-01",
                    "Data_Referencia": "2025-12-31",
                    "Versao": 7,
                    "ID_Documento": "123456",
                    "Nome_Empresarial": "PETROLEO BRASILEIRO S.A. PETROBRAS",
                    "Valor_Mobiliario": "Ações Preferenciais",
                    "Codigo_Negociacao": "PETR4",
                    "Mercado": "Bolsa",
                    "Sigla_Entidade_Administradora": "B3",
                    "Entidade_Administradora": "B3 S.A.",
                    "Data_Inicio_Negociacao": "2000-01-03",
                    "Data_Fim_Negociacao": None,
                    "Segmento": "Nível 2",
                }
            ]
        )


def test_live_fca_headers_map_cnpj_to_stable_cvm_identity() -> None:
    service = CVMIngestionService(collector=LiveFCACollector())  # type: ignore[arg-type]
    collected_at = datetime(2026, 8, 29, 19, tzinfo=UTC)

    issuers = service.load_issuer_master_from_bytes(
        b"registry",
        collected_at=collected_at,
        active_only=False,
    )
    securities = service.load_security_master_from_archive(
        b"fca",
        collected_at=collected_at,
    )

    assert issuers[0].company_id == "cvm:9512"
    assert len(securities) == 1
    security = securities[0]
    assert security.company_id == "cvm:9512"
    assert security.ticker == "PETR4"
    assert security.security_type == "Ações Preferenciais"
    assert security.market == "Bolsa"
    assert security.administrator == "B3"
    assert security.reference_date == date(2025, 12, 31)
    assert security.version == 7
    assert security.trading_start == date(2000, 1, 3)


def test_live_fca_ticker_without_registry_identity_fails_closed() -> None:
    service = CVMIngestionService(collector=LiveFCACollector())  # type: ignore[arg-type]

    with pytest.raises(ValueError, match="could not be mapped"):
        service.load_security_master_from_archive(
            b"fca",
            collected_at=datetime(2026, 8, 29, 19, tzinfo=UTC),
        )
