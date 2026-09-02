from __future__ import annotations

import warnings
from datetime import UTC, date, datetime
from typing import Any

import pandas as pd

from ultimate_stock_analyzer.domain.master import (
    FinancialStatementLine,
    IssuerRecord,
    SecurityRecord,
)

CVM_REGISTRY_URL = "https://dados.cvm.gov.br/dados/CIA_ABERTA/CAD/DADOS/cad_cia_aberta.csv"
_FILING_NATURAL_KEY = ("CD_CVM", "DT_REFER", "VERSAO")
_METADATA_FIELDS = ("ID_DOC", "DT_RECEB", "LINK_DOC")


def company_id_from_cvm_code(value: Any) -> str:
    return f"cvm:{_as_int(value)}"


def normalize_issuer_registry(
    frame: pd.DataFrame,
    *,
    collected_at: datetime,
    active_only: bool = True,
) -> list[IssuerRecord]:
    rows: list[IssuerRecord] = []
    for record in frame.to_dict(orient="records"):
        cvm_code = _as_int(_pick(record, "CD_CVM"))
        status = _as_text(_pick(record, "SIT"))
        if active_only and status and status.upper() not in {"ATIVO", "ATIVA"}:
            continue
        rows.append(
            IssuerRecord(
                company_id=f"cvm:{cvm_code}",
                cvm_code=cvm_code,
                cnpj=_as_text(_pick(record, "CNPJ_CIA", "CNPJ")),
                legal_name=_required_text(_pick(record, "DENOM_SOCIAL", "DENOM_CIA")),
                trade_name=_as_text(_pick(record, "DENOM_COMERC")),
                registration_status=status,
                registration_date=_as_date(_pick(record, "DT_REG")),
                cancellation_date=_as_date(_pick(record, "DT_CANCEL")),
                collected_at=_aware(collected_at),
            )
        )
    return rows


def normalize_fca_securities(
    frame: pd.DataFrame,
    *,
    collected_at: datetime,
    source_document: str,
) -> list[SecurityRecord]:
    """Normalize the CVM FCA security/ticker table.

    Current FCA files use descriptive CamelCase headers (for example,
    ``Codigo_Negociacao`` and ``Data_Referencia``), while older fixtures and
    historical extracts can use abbreviated uppercase names. Both are accepted.
    Identity must already be resolved to the official ``CD_CVM`` before this
    function is called; the ingestion service performs the CNPJ->CD_CVM join.
    """
    rows: list[SecurityRecord] = []
    for record in frame.to_dict(orient="records"):
        ticker = _as_text(
            _pick(
                record,
                "Codigo_Negociacao",
                "CODIGO_NEGOCIACAO",
                "CD_NEGOCIACAO",
                "COD_NEGOCIACAO",
                "CODIGO",
            )
        )
        if not ticker:
            continue
        cvm_code = _as_int(_pick(record, "CD_CVM"))
        available = _as_datetime(
            _pick(
                record,
                "DT_RECEB",
                "DT_RECEB_META",
                "Data_Recebimento",
                "Data_Entrega",
                "Data_Apresentacao",
                "DT_ENTREGA",
                "DT_APRESENTACAO",
            )
        )
        rows.append(
            SecurityRecord(
                company_id=f"cvm:{cvm_code}",
                ticker=ticker.upper(),
                isin=_as_text(_pick(record, "ISIN", "CD_ISIN", "Codigo_ISIN")),
                security_type=_as_text(
                    _pick(
                        record,
                        "Valor_Mobiliario",
                        "TP_VALOR_MOBILIARIO",
                        "DS_VALOR_MOBILIARIO",
                    )
                ),
                market=_as_text(_pick(record, "Mercado", "DS_MERCADO", "MERCADO")),
                administrator=_as_text(
                    _pick(
                        record,
                        "Sigla_Entidade_Administradora",
                        "Entidade_Administradora",
                        "SG_ENTID_ADMIN",
                        "ENTIDADE_ADMINISTRADORA",
                    )
                ),
                trading_start=_as_date(
                    _pick(
                        record,
                        "Data_Inicio_Negociacao",
                        "DT_INI_NEGOCIACAO",
                        "DT_INICIO_NEGOCIACAO",
                    )
                ),
                trading_end=_as_date(
                    _pick(
                        record,
                        "Data_Fim_Negociacao",
                        "DT_FIM_NEGOCIACAO",
                        "DT_TERMINO_NEGOCIACAO",
                    )
                ),
                reference_date=_as_date(
                    _pick(record, "Data_Referencia", "DT_REFER")
                ),
                version=_as_int(_pick(record, "Versao", "VERSAO"), default=0),
                available_from=available,
                collected_at=_aware(collected_at),
                source_document=source_document,
            )
        )
    return rows


def attach_document_metadata(
    statement_frame: pd.DataFrame,
    metadata_frame: pd.DataFrame,
    *,
    strict_natural_key: bool = False,
) -> pd.DataFrame:
    """Attach official filing metadata without inventing publication timestamps.

    CVM statement members normally do not carry ``ID_DOC``. The yearly DFP/ITR
    summary member does, so direct document-id joins remain preferred whenever
    both sides expose the identifier. Otherwise the official filing key
    ``CD_CVM + DT_REFER + VERSAO`` is used as a fallback.

    Only metadata keys represented in the statement frame are considered. A
    relevant natural key can legitimately map to multiple official documents.
    When its metadata is not unique, only field-level consensus is propagated.
    If ``DT_RECEB`` itself conflicts, all fallback metadata for that key is
    suppressed so the affected statement rows remain non-PIT instead of choosing
    an earlier or later publication timestamp. Callers performing exact-issuer
    contract validation can set ``strict_natural_key=True`` to reject relevant
    fallback ambiguity entirely. Direct ``ID_DOC`` ambiguity always remains
    strict because an exact document identifier must be unique.
    """
    if metadata_frame.empty:
        return statement_frame.copy()

    if "ID_DOC" in statement_frame.columns and "ID_DOC" in metadata_frame.columns:
        return _merge_document_metadata(
            statement_frame,
            metadata_frame,
            join_keys=("ID_DOC",),
        )

    if not all(column in statement_frame.columns for column in _FILING_NATURAL_KEY):
        return statement_frame.copy()
    if not all(column in metadata_frame.columns for column in _FILING_NATURAL_KEY):
        return statement_frame.copy()

    statement = statement_frame.copy()
    metadata = metadata_frame.copy()
    join_keys = ("__CVM_CODE", "__REFERENCE_DATE", "__VERSION")
    statement[join_keys[0]] = _normalized_cvm_code(statement["CD_CVM"])
    statement[join_keys[1]] = _normalized_reference_date(statement["DT_REFER"])
    statement[join_keys[2]] = _normalized_version(statement["VERSAO"])
    metadata[join_keys[0]] = _normalized_cvm_code(metadata["CD_CVM"])
    metadata[join_keys[1]] = _normalized_reference_date(metadata["DT_REFER"])
    metadata[join_keys[2]] = _normalized_version(metadata["VERSAO"])
    metadata = _filter_metadata_to_statement_keys(
        statement,
        metadata,
        join_keys=join_keys,
    )
    if not strict_natural_key:
        metadata = _collapse_natural_key_metadata(metadata, join_keys=join_keys)

    merged = _merge_document_metadata(statement, metadata, join_keys=join_keys)
    return merged.drop(columns=list(join_keys))


def _filter_metadata_to_statement_keys(
    statement_frame: pd.DataFrame,
    metadata_frame: pd.DataFrame,
    *,
    join_keys: tuple[str, ...],
) -> pd.DataFrame:
    relevant_keys = statement_frame[list(join_keys)].drop_duplicates()
    return metadata_frame.merge(
        relevant_keys,
        on=list(join_keys),
        how="inner",
        validate="many_to_one",
    )


def _collapse_natural_key_metadata(
    metadata_frame: pd.DataFrame,
    *,
    join_keys: tuple[str, ...],
) -> pd.DataFrame:
    metadata_columns = [*join_keys]
    metadata_columns.extend(
        column
        for column in _METADATA_FIELDS
        if column in metadata_frame.columns and column not in join_keys
    )
    metadata = metadata_frame[metadata_columns].drop_duplicates()
    if metadata.empty:
        return metadata

    collapsed: list[dict[str, Any]] = []
    ambiguous_keys: list[dict[str, Any]] = []
    publication_time_conflicts = 0
    metadata_fields = [
        column for column in _METADATA_FIELDS if column in metadata.columns
    ]

    for key_values, group in metadata.groupby(
        list(join_keys),
        dropna=False,
        sort=False,
    ):
        if not isinstance(key_values, tuple):
            key_values = (key_values,)
        row = dict(zip(join_keys, key_values, strict=True))
        conflicting_fields: list[str] = []

        for field in metadata_fields:
            distinct = group[field].dropna().drop_duplicates()
            if len(distinct) == 1:
                row[field] = distinct.iloc[0]
            else:
                row[field] = pd.NA
                if len(distinct) > 1:
                    conflicting_fields.append(field)

        if "DT_RECEB" in conflicting_fields:
            publication_time_conflicts += 1
            for field in metadata_fields:
                row[field] = pd.NA

        if conflicting_fields:
            ambiguous_keys.append(
                {
                    **{key: row[key] for key in join_keys},
                    "fields": tuple(conflicting_fields),
                }
            )
        collapsed.append(row)

    if ambiguous_keys:
        examples = ambiguous_keys[:3]
        warnings.warn(
            "CVM natural-key filing metadata is ambiguous; conflicting fallback "
            "metadata was suppressed instead of selecting an arbitrary document: "
            f"count={len(ambiguous_keys)} "
            f"publication_time_conflicts={publication_time_conflicts} "
            f"examples={examples}",
            RuntimeWarning,
            stacklevel=2,
        )

    return pd.DataFrame(collapsed, columns=metadata_columns)


def _merge_document_metadata(
    statement_frame: pd.DataFrame,
    metadata_frame: pd.DataFrame,
    *,
    join_keys: tuple[str, ...],
) -> pd.DataFrame:
    metadata_columns = [*join_keys]
    metadata_columns.extend(
        column
        for column in _METADATA_FIELDS
        if column in metadata_frame.columns and column not in join_keys
    )
    metadata = metadata_frame[metadata_columns].drop_duplicates()
    duplicated = metadata.duplicated(subset=list(join_keys), keep=False)
    if duplicated.any():
        examples = metadata.loc[duplicated, list(join_keys)].head(3).to_dict("records")
        raise ValueError(
            "ambiguous CVM filing metadata for join key; "
            f"examples={examples}"
        )
    return statement_frame.merge(
        metadata,
        on=list(join_keys),
        how="left",
        suffixes=("", "_META"),
        validate="many_to_one",
    )


def _normalized_cvm_code(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").astype("Int64")


def _normalized_reference_date(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, errors="coerce").dt.strftime("%Y-%m-%d")


def _normalized_version(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").astype("Int64")


def normalize_statement(
    frame: pd.DataFrame,
    *,
    document_type: str,
    statement: str,
    collected_at: datetime,
    source_document: str,
) -> list[FinancialStatementLine]:
    rows: list[FinancialStatementLine] = []
    for record in frame.to_dict(orient="records"):
        cvm_code = _as_int(_pick(record, "CD_CVM"))
        raw_value = _as_float(_pick(record, "VL_CONTA"))
        scale = _as_text(_pick(record, "ESCALA_MOEDA"))
        value_brl = raw_value * _scale_multiplier(scale)
        received = _as_datetime(
            _pick(record, "DT_RECEB", "DT_RECEB_META", "DT_ENTREGA")
        )
        reference_date = _required_date(_pick(record, "DT_REFER"))
        rows.append(
            FinancialStatementLine(
                company_id=f"cvm:{cvm_code}",
                cvm_code=cvm_code,
                cnpj=_as_text(_pick(record, "CNPJ_CIA")),
                company_name=_required_text(
                    _pick(record, "DENOM_CIA", "DENOM_SOCIAL")
                ),
                document_type=document_type.upper(),
                statement=statement.upper(),
                consolidation_scope=_as_text(_pick(record, "GRUPO_DFP")),
                reference_date=reference_date,
                period_start=_as_date(_pick(record, "DT_INI_EXERC")),
                period_end=_as_date(_pick(record, "DT_FIM_EXERC")) or reference_date,
                fiscal_order=_as_text(_pick(record, "ORDEM_EXERC")),
                account_code=_required_text(_pick(record, "CD_CONTA")),
                account_name=_required_text(_pick(record, "DS_CONTA")),
                value_brl=value_brl,
                source_scale=scale,
                version=_as_int(_pick(record, "VERSAO"), default=0),
                document_id=_as_int_or_none(_pick(record, "ID_DOC")),
                received_at=received,
                available_from=received,
                collected_at=_aware(collected_at),
                source_document=source_document,
            )
        )
    return rows


def point_in_time_lines(
    lines: list[FinancialStatementLine],
    *,
    as_of: datetime,
) -> list[FinancialStatementLine]:
    cutoff = _aware(as_of)
    eligible = [
        line
        for line in lines
        if line.available_from is not None and _aware(line.available_from) <= cutoff
    ]
    winners: dict[
        tuple[str, str, str, str | None, date, str, str | None],
        FinancialStatementLine,
    ] = {}
    for line in eligible:
        key = (
            line.company_id,
            line.document_type,
            line.statement,
            line.consolidation_scope,
            line.reference_date,
            line.account_code,
            line.fiscal_order,
        )
        current = winners.get(key)
        if current is None or _line_rank(line) > _line_rank(current):
            winners[key] = line
    return sorted(
        winners.values(),
        key=lambda item: (
            item.company_id,
            item.reference_date,
            item.statement,
            item.account_code,
            item.fiscal_order or "",
        ),
    )


def _line_rank(line: FinancialStatementLine) -> tuple[datetime, int]:
    assert line.available_from is not None
    return _aware(line.available_from), line.version


def _scale_multiplier(scale: str | None) -> float:
    normalized = (scale or "").strip().upper()
    if normalized in {"MIL", "MILHAR", "MILHARES"}:
        return 1_000.0
    if normalized in {"MILHAO", "MILHÃO", "MILHOES", "MILHÕES"}:
        return 1_000_000.0
    return 1.0


def _pick(record: dict[str, Any], *names: str) -> Any:
    for name in names:
        if name in record and not pd.isna(record[name]):
            return record[name]
    return None


def _as_text(value: Any) -> str | None:
    if value is None or pd.isna(value):
        return None
    text = str(value).strip()
    return text or None


def _required_text(value: Any) -> str:
    text = _as_text(value)
    if text is None:
        raise ValueError("required text value is missing")
    return text


def _as_int(value: Any, *, default: int | None = None) -> int:
    if value is None or pd.isna(value):
        if default is not None:
            return default
        raise ValueError("required integer value is missing")
    return int(float(value))


def _as_int_or_none(value: Any) -> int | None:
    if value is None or pd.isna(value):
        return None
    return int(float(value))


def _as_float(value: Any) -> float:
    if value is None or pd.isna(value):
        raise ValueError("required numeric value is missing")
    if isinstance(value, str):
        normalized = value.strip().replace(".", "").replace(",", ".")
        return float(normalized)
    return float(value)


def _as_date(value: Any) -> date | None:
    if value is None or pd.isna(value):
        return None
    return pd.to_datetime(value, dayfirst=False).date()


def _required_date(value: Any) -> date:
    parsed = _as_date(value)
    if parsed is None:
        raise ValueError("required date value is missing")
    return parsed


def _as_datetime(value: Any) -> datetime | None:
    if value is None or pd.isna(value):
        return None
    parsed = pd.to_datetime(value, dayfirst=False)
    if parsed.tzinfo is None:
        return parsed.to_pydatetime().replace(tzinfo=UTC)
    return parsed.to_pydatetime().astimezone(UTC)


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
