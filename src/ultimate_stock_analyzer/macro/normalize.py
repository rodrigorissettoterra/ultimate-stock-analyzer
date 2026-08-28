from __future__ import annotations

import math
from datetime import date

from ultimate_stock_analyzer.macro.models import MacroFactor, MacroObservation


def normalize_bcb_sgs_rows(
    rows: list[dict[str, str]],
    *,
    factor: MacroFactor,
    series_code: int,
    unit: str,
    publication_date: date | None = None,
) -> list[MacroObservation]:
    observations: list[MacroObservation] = []
    for row in rows:
        raw_date = row.get("data")
        raw_value = row.get("valor")
        if raw_date is None or raw_value is None:
            continue
        value = _number(raw_value)
        if value is None:
            continue
        observations.append(
            MacroObservation(
                factor=factor,
                value=value,
                reference_date=_brazilian_date(raw_date),
                unit=unit,
                source="BCB_SGS",
                source_series=str(series_code),
                publication_date=publication_date,
            )
        )
    return sorted(observations, key=lambda item: item.reference_date)


def normalize_sidra_rows(
    rows: list[dict[str, str]],
    *,
    factor: MacroFactor,
    table: int,
    period_key: str,
    value_key: str = "V",
    unit: str,
    publication_date: date | None = None,
) -> list[MacroObservation]:
    """Normalize a selected SIDRA result after the caller chooses table/dimensions explicitly.

    Period values supported by this generic normalizer are YYYY, YYYYMM and YYYYQn forms.
    SIDRA special/missing value markers are skipped rather than converted to zero.
    """
    observations: list[MacroObservation] = []
    for row in rows:
        raw_period = row.get(period_key)
        raw_value = row.get(value_key)
        if not raw_period or raw_value is None:
            continue
        value = _number(raw_value)
        if value is None:
            continue
        try:
            reference_date = _period_date(raw_period)
        except ValueError:
            continue
        observations.append(
            MacroObservation(
                factor=factor,
                value=value,
                reference_date=reference_date,
                unit=unit,
                source="IBGE_SIDRA",
                source_series=str(table),
                publication_date=publication_date,
            )
        )
    return sorted(observations, key=lambda item: item.reference_date)


def _brazilian_date(value: str) -> date:
    day, month, year = (int(part) for part in value.strip().split("/"))
    return date(year, month, day)


def _period_date(value: str) -> date:
    text = value.strip().upper()
    if len(text) == 4 and text.isdigit():
        return date(int(text), 12, 31)
    if len(text) == 6 and text.isdigit():
        return date(int(text[:4]), int(text[4:]), 1)
    if len(text) == 6 and text[4] == "Q" and text[5] in "1234":
        quarter = int(text[5])
        return date(int(text[:4]), 1 + (quarter - 1) * 3, 1)
    raise ValueError(f"unsupported macro period: {value!r}")


def _number(value: str) -> float | None:
    text = value.strip().replace(" ", "")
    if text in {"", "-", "..", "...", "X"}:
        return None
    if "," in text:
        text = text.replace(".", "").replace(",", ".")
    try:
        parsed = float(text)
    except ValueError:
        return None
    return parsed if math.isfinite(parsed) else None
