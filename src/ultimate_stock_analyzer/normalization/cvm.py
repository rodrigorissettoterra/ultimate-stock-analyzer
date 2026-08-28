from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any

import pandas as pd

from ultimate_stock_analyzer.domain.master import (
    FinancialStatementLine,
    IssuerRecord,
    SecurityRecord,
)

CVM_REGISTRY_URL = "https://dados.cvm.gov.br/dados/CIA_ABERTA/CAD/DADOS/cad_cia_aberta.csv"


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
    rows: list[SecurityRecord] = []
    for record in frame.to_dict(orient="records"):
        ticker = _as_text(
            _pick(
                record,
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
            _pick(record, "DT_RECEB", "DT_ENTREGA", "DT_APRESENTACAO")
        )
        rows.append(
            SecurityRecord(
                company_id=f"cvm:{cvm_code}",
                ticker=ticker.upper(),
                isin=_as_text(_pick(record, "ISIN", "CD_ISIN")),
                security_type=_as_text(
                    _pick(record, "TP_VALOR_MOBILIARIO", "DS_VALOR_MOBILIARIO")
                ),
                market=_as_text(_pick(record, "DS_MERCADO", "MERCADO")),
                administrator=_as_text(
                    _pick(record, "SG_ENTID_ADMIN", "ENTIDADE_ADMINISTRADORA")
                ),
                trading_start=_as_date(
                    _pick(record, "DT_INI_NEGOCIACAO", "DT_INICIO_NEGOCIACAO")
                ),
                trading_end=_as_date(
                    _pick(record, "DT_FIM_NEGOCIACAO", "DT_TERMINO_NEGOCIACAO")
                ),
                reference_date=_as_date(_pick(record, "DT_REFER")),
                version=_as_int(_pick(record, "VERSAO"), default=0),
                available_from=available,
                collected_at=_aware(collected_at),
                source_document=source_document,
            )
        )
    return rows


def attach_document_metadata(
    statement_frame: pd.DataFrame,
    metadata_frame: pd.DataFrame,
) -> pd.DataFrame:
    if "ID_DOC" not in statement_frame.columns or "ID_DOC" not in metadata_frame.columns:
        return statement_frame.copy()

    metadata_columns = [
        column
        for column in ("ID_DOC", "DT_RECEB", "LINK_DOC")
        if column in metadata_frame.columns
    ]
    metadata = metadata_frame[metadata_columns].drop_duplicates(subset=["ID_DOC"], keep="last")
    return statement_frame.merge(metadata, on="ID_DOC", how="left", suffixes=("", "_META"))


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
                company_name=_required_text(_pick(record, "DENOM_CIA", "DENOM_SOCIAL")),
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
    winners: dict[tuple[str, str, str, date, str, str | None], FinancialStatementLine] = {}
    for line in eligible:
        key = (
            line.company_id,
            line.document_type,
            line.statement,
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
