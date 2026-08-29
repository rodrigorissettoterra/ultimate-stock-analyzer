from __future__ import annotations

from datetime import UTC, datetime

import pandas as pd

import ultimate_stock_analyzer.orchestration.cvm_ingestion as ingestion_module
from ultimate_stock_analyzer.orchestration.cvm_ingestion import CVMIngestionService


class FakeCollector:
    def __init__(self) -> None:
        self.downloads = 0

    def download_zip(self, document: str, year: int) -> bytes:
        self.downloads += 1
        return b"archive"

    def list_csv_files(self, archive: bytes) -> list[str]:
        return ["dfp_cia_aberta_2024.csv"]

    def find_csv(self, archive: bytes, *tokens: str) -> str:
        return "_".join(tokens) + ".csv"

    def read_csv(self, archive: bytes, filename: str) -> pd.DataFrame:
        if filename == "dfp_cia_aberta_2024.csv":
            return pd.DataFrame({"ID_DOC": [1], "DT_RECEB": ["2025-03-01"]})
        return pd.DataFrame({"ID_DOC": [1]})


def test_load_statements_downloads_one_archive(monkeypatch) -> None:
    collector = FakeCollector()
    service = CVMIngestionService(collector=collector)  # type: ignore[arg-type]

    monkeypatch.setattr(
        ingestion_module,
        "normalize_statement",
        lambda frame, **kwargs: [kwargs["statement"]],
    )

    rows = service.load_statements(
        document_type="DFP",
        year=2024,
        statements=("BPA", "DRE", "DFC_MI"),
        scope_token="con",
        collected_at=datetime(2025, 3, 2, tzinfo=UTC),
    )

    assert collector.downloads == 1
    assert rows == ["BPA", "DRE", "DFC_MI"]
