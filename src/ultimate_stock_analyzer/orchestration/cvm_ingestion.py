from __future__ import annotations

import warnings
from datetime import datetime
from typing import Any

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
        self._cvm_code_by_cnpj: dict[str, int] = {}
        self.last_unmapped_security_tickers: tuple[str, ...] = ()

    def load_issuer_master(
        self,
        *,
        collected_at: datetime,
        active_only: bool = True,
    ) -> list[IssuerRecord]:
        return self.load_issuer_master_from_bytes(
            self.collector.download_registry_bytes(),
            collected_at=collected_at,
            active_only=active_only,
        )

    def load_issuer_master_from_bytes(
        self,
        content: bytes,
        *,
        collected_at: datetime,
        active_only: bool = True,
    ) -> list[IssuerRecord]:
        frame = self.collector.read_registry_bytes(content)
        issuers = normalize_issuer_registry(
            frame,
            collected_at=collected_at,
            active_only=active_only,
        )
        self._cache_issuer_identity(issuers)
        return issuers

    def load_security_master(
        self,
        *,
        year: int,
        collected_at: datetime,
    ) -> list[SecurityRecord]:
        if not self._cvm_code_by_cnpj:
            self.load_issuer_master(
                collected_at=collected_at,
                active_only=False,
            )
        archive = self.collector.download_zip("FCA", year)
        return self.load_security_master_from_archive(
            archive,
            collected_at=collected_at,
        )

    def load_security_master_from_archive(
        self,
        archive: bytes,
        *,
        collected_at: datetime,
    ) -> list[SecurityRecord]:
        security_file = self.collector.find_csv(archive, "valor_mobiliario")
        securities = self.collector.read_csv(archive, security_file)
        securities = self._attach_cvm_codes(securities)
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
        return self.load_statements(
            document_type=document_type,
            year=year,
            statements=(statement,),
            scope_token=scope_token,
            collected_at=collected_at,
        )

    def load_statements(
        self,
        *,
        document_type: str,
        year: int,
        statements: tuple[str, ...],
        scope_token: str,
        collected_at: datetime,
    ) -> list[FinancialStatementLine]:
        archive = self.collector.download_zip(document_type.upper(), year)
        return self.load_statements_from_archive(
            archive,
            document_type=document_type,
            statements=statements,
            scope_token=scope_token,
            collected_at=collected_at,
        )

    def load_statements_from_archive(
        self,
        archive: bytes,
        *,
        document_type: str,
        statements: tuple[str, ...],
        scope_token: str,
        collected_at: datetime,
    ) -> list[FinancialStatementLine]:
        document = document_type.upper()
        metadata = self._read_metadata(archive, f"{document.lower()}_cia_aberta")
        output: list[FinancialStatementLine] = []
        for statement in statements:
            statement_file = self.collector.find_csv(
                archive,
                statement.lower(),
                scope_token.lower(),
            )
            statement_frame = self.collector.read_csv(archive, statement_file)
            statement_frame = attach_document_metadata(statement_frame, metadata)
            output.extend(
                normalize_statement(
                    statement_frame,
                    document_type=document,
                    statement=statement,
                    collected_at=collected_at,
                    source_document=statement_file,
                )
            )
        return output

    def load_company_statements_from_archive(
        self,
        archive: bytes,
        *,
        cvm_code: int,
        document_type: str,
        statements: tuple[str, ...],
        scope_token: str,
        collected_at: datetime,
    ) -> list[FinancialStatementLine]:
        """Load one issuer's statements with strict filing-lineage semantics.

        Exact-issuer contract audits must not inherit metadata ambiguity from
        unrelated issuers, nor may they collapse multiple official documents
        that share a CVM natural key. Both statement and metadata frames are
        scoped to ``cvm_code`` before attachment, and the natural-key fallback
        is strict so relevant ambiguity raises instead of being suppressed.
        """
        document = document_type.upper()
        metadata = self._read_metadata(archive, f"{document.lower()}_cia_aberta")
        metadata = _filter_cvm_code(metadata, cvm_code=cvm_code)
        output: list[FinancialStatementLine] = []
        for statement in statements:
            statement_file = self.collector.find_csv(
                archive,
                statement.lower(),
                scope_token.lower(),
            )
            statement_frame = self.collector.read_csv(archive, statement_file)
            if "CD_CVM" not in statement_frame.columns:
                raise ValueError(
                    f"CVM statement member {statement_file!r} has no CD_CVM column"
                )
            statement_frame = _filter_cvm_code(
                statement_frame,
                cvm_code=cvm_code,
            )
            if statement_frame.empty:
                continue
            statement_frame = attach_document_metadata(
                statement_frame,
                metadata,
                strict_natural_key=True,
            )
            output.extend(
                normalize_statement(
                    statement_frame,
                    document_type=document,
                    statement=statement,
                    collected_at=collected_at,
                    source_document=statement_file,
                )
            )
        return output

    def _cache_issuer_identity(self, issuers: list[IssuerRecord]) -> None:
        for issuer in issuers:
            key = _cnpj_key(issuer.cnpj)
            if key is not None:
                self._cvm_code_by_cnpj[key] = issuer.cvm_code

    def _attach_cvm_codes(self, frame: pd.DataFrame) -> pd.DataFrame:
        output = frame.copy()
        if "CD_CVM" not in output.columns:
            output["CD_CVM"] = pd.NA

        ticker_column = _first_column(
            output,
            "Codigo_Negociacao",
            "CODIGO_NEGOCIACAO",
            "CD_NEGOCIACAO",
            "COD_NEGOCIACAO",
            "CODIGO",
        )
        cnpj_column = _first_column(
            output,
            "CNPJ_Companhia",
            "CNPJ_CIA",
            "CNPJ",
        )

        if cnpj_column is not None and self._cvm_code_by_cnpj:
            missing_code = output["CD_CVM"].isna()
            output.loc[missing_code, "CD_CVM"] = output.loc[
                missing_code, cnpj_column
            ].map(lambda value: self._cvm_code_by_cnpj.get(_cnpj_key(value) or ""))

        self.last_unmapped_security_tickers = ()
        if ticker_column is not None:
            ticker_text = output[ticker_column].fillna("").astype(str).str.strip()
            unresolved = ticker_text.ne("") & output["CD_CVM"].isna()
            if unresolved.any():
                unmapped = tuple(sorted(set(ticker_text[unresolved].tolist())))
                self.last_unmapped_security_tickers = unmapped
                warnings.warn(
                    "Excluding FCA ticker rows without an official CVM issuer identity: "
                    f"count={int(unresolved.sum())} examples={', '.join(unmapped[:5])}",
                    RuntimeWarning,
                    stacklevel=2,
                )
                output = output.loc[~unresolved].copy()
        return output

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


def _filter_cvm_code(frame: pd.DataFrame, *, cvm_code: int) -> pd.DataFrame:
    if frame.empty:
        return frame.copy()
    if "CD_CVM" not in frame.columns:
        return frame.copy()
    normalized = pd.to_numeric(frame["CD_CVM"], errors="coerce")
    return frame.loc[normalized.eq(cvm_code)].copy()


def _first_column(frame: pd.DataFrame, *names: str) -> str | None:
    return next((name for name in names if name in frame.columns), None)


def _cnpj_key(value: Any) -> str | None:
    if value is None or pd.isna(value):
        return None
    digits = "".join(character for character in str(value) if character.isdigit())
    return digits or None
