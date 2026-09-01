from __future__ import annotations

from datetime import datetime

import pandas as pd

from ultimate_stock_analyzer.collectors.cvm import CVMCollector
from ultimate_stock_analyzer.domain.master import FinancialStatementLine
from ultimate_stock_analyzer.normalization.cvm import (
    attach_document_metadata,
    normalize_statement,
)


def load_company_statements_from_archive(
    archive: bytes,
    *,
    cvm_code: int,
    document_type: str,
    statements: tuple[str, ...],
    scope_token: str,
    collected_at: datetime,
    collector: CVMCollector | None = None,
) -> list[FinancialStatementLine]:
    """Normalize one CVM issuer and reject ambiguous filing lineage."""

    source = collector or CVMCollector()
    document = document_type.upper()
    metadata = _read_metadata_for_company(
        source,
        archive,
        prefix=f"{document.lower()}_cia_aberta",
        cvm_code=cvm_code,
    )

    output: list[FinancialStatementLine] = []
    for statement in statements:
        statement_file = source.find_csv(
            archive,
            statement.lower(),
            scope_token.lower(),
        )
        frame = source.read_csv(archive, statement_file)
        frame = _filter_cvm_code(frame, cvm_code)
        if frame.empty:
            continue
        frame = attach_document_metadata(
            frame,
            metadata,
            strict_natural_key=True,
        )
        output.extend(
            normalize_statement(
                frame,
                document_type=document,
                statement=statement,
                collected_at=collected_at,
                source_document=statement_file,
            )
        )
    return output


def _read_metadata_for_company(
    collector: CVMCollector,
    archive: bytes,
    *,
    prefix: str,
    cvm_code: int,
) -> pd.DataFrame:
    candidates = [
        filename
        for filename in collector.list_csv_files(archive)
        if filename.lower().startswith(prefix.lower())
        and filename.lower().count("_") <= prefix.count("_") + 2
    ]
    for filename in candidates:
        frame = collector.read_csv(archive, filename)
        if {"ID_DOC", "DT_RECEB"}.issubset(frame.columns):
            return _filter_cvm_code(frame, cvm_code)
    return pd.DataFrame()


def _filter_cvm_code(frame: pd.DataFrame, cvm_code: int) -> pd.DataFrame:
    if "CD_CVM" not in frame.columns:
        raise ValueError("CVM frame is missing CD_CVM")
    normalized = pd.to_numeric(frame["CD_CVM"], errors="coerce")
    return frame.loc[normalized.eq(cvm_code)].copy()
