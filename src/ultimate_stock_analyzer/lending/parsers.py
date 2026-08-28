from __future__ import annotations

import csv
import io
import math
from datetime import date

from ultimate_stock_analyzer.lending.models import (
    LendingOpenPositionRecord,
    LoanBalanceRecord,
)


def parse_loan_balance_csv(text: str, *, delimiter: str = ";") -> list[LoanBalanceRecord]:
    """Parse B3 LoanBalanceFile-style CSV data using official field tags."""
    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
    return [loan_balance_from_row(row) for row in reader if _value(row, "TckrSymb", "Código IF")]


def parse_lending_open_position_csv(
    text: str,
    *,
    delimiter: str = ";",
) -> list[LendingOpenPositionRecord]:
    """Parse B3 LendingOpenPositionFile-style CSV data using official field tags."""
    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
    return [
        open_position_from_row(row)
        for row in reader
        if _value(row, "TckrSymb", "Código IF")
    ]


def loan_balance_from_row(row: dict[str, str | None]) -> LoanBalanceRecord:
    return LoanBalanceRecord(
        report_date=_parse_date(_required(row, "RptDt", "Data")),
        ticker=_required(row, "TckrSymb", "Código IF").strip().upper(),
        isin=_optional_text(_value(row, "ISIN", "Código ISIN")),
        asset=_optional_text(_value(row, "Asst", "Ativo", "Empresa ou fundo")),
        market=_optional_text(_value(row, "MktNm", "Mercado")),
        contracts_day=_parse_int(_value(row, "QtyCtrctsDay", "Número de contratos")),
        shares_day=_parse_number(_value(row, "QtyShrDay", "Quantidade de ativos")) or 0.0,
        value_day=_parse_number(_value(row, "ValCtrctsDay", "Valor em R$")) or 0.0,
        donor_min_rate=_parse_rate(_value(row, "DnrMinRate", "Taxa doador mínima")),
        donor_avg_rate=_parse_rate(
            _value(row, "DnrAvrgRate", "Taxa doador média ponderada", "Taxa média doador")
        ),
        donor_max_rate=_parse_rate(_value(row, "DnrMaxRate", "Taxa doador máxima")),
        taker_min_rate=_parse_rate(_value(row, "TakrMinRate", "Taxa tomador mínima")),
        taker_avg_rate=_parse_rate(
            _value(row, "TakrAvrgRate", "Taxa tomador média ponderada", "Taxa média tomador")
        ),
        taker_max_rate=_parse_rate(_value(row, "TakrMaxRate", "Taxa tomador máxima")),
    )


def open_position_from_row(row: dict[str, str | None]) -> LendingOpenPositionRecord:
    return LendingOpenPositionRecord(
        report_date=_parse_date(_required(row, "RptDt", "Data")),
        ticker=_required(row, "TckrSymb", "Código IF").strip().upper(),
        isin=_optional_text(_value(row, "ISIN", "Código ISIN")),
        asset=_optional_text(_value(row, "Asst", "Ativo", "Empresa ou fundo")),
        balance_quantity=_parse_number(
            _required(row, "BalQty", "Saldo em quantidade do ativo")
        )
        or 0.0,
        trade_average_price=_parse_number(_value(row, "TradAvrgPric", "Preço médio")),
        price_factor=_parse_number(_value(row, "PricFctr", "Fator de preço")),
        balance_value=_parse_number(_value(row, "BalVal", "Saldo em R$")),
        market=_optional_text(_value(row, "MktNm", "Mercado")),
    )


def _value(row: dict[str, str | None], *aliases: str) -> str | None:
    normalized = {str(key).strip().casefold(): value for key, value in row.items() if key is not None}
    for alias in aliases:
        value = normalized.get(alias.strip().casefold())
        if value is not None and value.strip() not in {"", "-"}:
            return value.strip()
    return None


def _required(row: dict[str, str | None], *aliases: str) -> str:
    value = _value(row, *aliases)
    if value is None:
        raise ValueError(f"required B3 field missing: {aliases[0]}")
    return value


def _optional_text(value: str | None) -> str | None:
    return value.strip() if value is not None and value.strip() else None


def _parse_date(value: str) -> date:
    text = value.strip()
    if "/" in text:
        day, month, year = (int(part) for part in text.split("/"))
        return date(year, month, day)
    if "-" in text:
        return date.fromisoformat(text[:10])
    if len(text) == 8 and text.isdigit():
        return date(int(text[:4]), int(text[4:6]), int(text[6:8]))
    raise ValueError(f"unsupported B3 date: {value!r}")


def _parse_int(value: str | None) -> int:
    parsed = _parse_number(value)
    return int(parsed) if parsed is not None else 0


def _parse_number(value: str | None) -> float | None:
    if value is None:
        return None
    text = value.strip().replace(" ", "")
    if text in {"", "-"}:
        return None
    text = text.replace("R$", "").replace("%", "")
    if "," in text:
        text = text.replace(".", "").replace(",", ".")
    try:
        parsed = float(text)
    except ValueError as exc:
        raise ValueError(f"invalid B3 numeric value: {value!r}") from exc
    return parsed if math.isfinite(parsed) else None


def _parse_rate(value: str | None) -> float | None:
    if value is None:
        return None
    parsed = _parse_number(value)
    if parsed is None:
        return None
    # B3 publishes lending rates as percentage points (for example, 5,00%).
    return parsed / 100.0
