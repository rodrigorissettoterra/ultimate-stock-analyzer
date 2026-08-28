from __future__ import annotations

from datetime import datetime

import pandas as pd

from ultimate_stock_analyzer.collectors.cvm import CVMCollector
from ultimate_stock_analyzer.domain.master import (
    FinancialStatementLine,
    IssuerRecord,
    SecurityRecord,
)
from ultimate_stock_analyzer.normalization.cvm import (
    attach_document_metadata,
    normalize_fca_securities,
    normalize_issuer_registry,
    normalize_statement,
)


class CVMIngestionService:
    def __init__(self, collector: CVMCollector | None = None) -> None:
        self.collector = collector or CVMCollector()

    def load_issuer_master(
        self,
        *,
        collected_at: datetime,
        active_only: bool = True,
    ) -> list[IssuerRecord]:
        frame = self.collector.download_registry()
        return normalize_issuer_registry(
            frame,
            collected_at=collected_at,
            active_only=active_only,
        )

    def load_security_master(
        self,
        *,
        year: int,
        collected_at: datetime,
    ) -> list[SecurityRecord]:
        archive = self.collector.download_zip("FCA", year)
        security_file = self.collector.find_csv(archive, "valor_mobiliario")
        securities = self.collector.read_csv(archive, security_file)
        metadata = self._read_metadata(archive, "fca_cia_aberta")
        securities = attach_document_metadata(securities, metadata)
        return normalize_fca_securities(
            securities,
            collected_at=collected_at,
            source_document=security_file,
        )

    def load_statement(
        self,
        *,
        document_type: str,
        year: int,
        statement: str,
        scope_token: str,
        collected_at: datetime,
    ) -> list[FinancialStatementLine]:
        document = document_type.upper()
        archive = self.collector.download_zip(document, year)
        statement_file = self.collector.find_csv(
            archive,
            statement.lower(),
            scope_token.lower(),
        )
        statement_frame = self.collector.read_csv(archive, statement_file)
        metadata = self._read_metadata(archive, f"{document.lower()}_cia_aberta")
        statement_frame = attach_document_metadata(statement_frame, metadata)
        return normalize_statement(
            statement_frame,
            document_type=document,
            statement=statement,
            collected_at=collected_at,
            source_document=statement_file,
        )

    def _read_metadata(self, archive: bytes, prefix: str) -> pd.DataFrame:
        candidates = [
            filename
            for filename in self.collector.list_csv_files(archive)
            if filename.lower().startswith(prefix.lower())
            and filename.lower().count("_") <= prefix.count("_") + 2
        ]
        for filename in candidates:
            frame = self.collector.read_csv(archive, filename)
            if {"ID_DOC", "DT_RECEB"}.issubset(frame.columns):
                return frame
        return pd.DataFrame()
