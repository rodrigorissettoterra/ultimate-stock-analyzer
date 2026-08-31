from __future__ import annotations

from dataclasses import dataclass
from math import isfinite

import pandas as pd

_REQUIRED_COLUMNS = ("coenti", "damesano", "plajustado", "CMR")


@dataclass(frozen=True, slots=True)
class InsuranceCapitalMetrics:
    """Verified SUSEP prudential capital evidence for one supervised insurer.

    SUSEP requires adjusted equity (PLA) to be sufficient relative to capital minimum
    required (CMR), and describes the principal solvency comparison in terms of PLA
    versus CMR. The score-facing ratio is therefore PLA / CMR: values below 1 indicate
    regulatory capital insufficiency. Current SES history is revision-prone, so the
    derived metric is not eligible for strict point-in-time backtests.
    """

    susep_company_code: str
    fiscal_year: int
    reference_period: int
    adjusted_equity: float | None
    capital_minimum_required: float | None
    capital_surplus: float | None
    solvency_ratio: float | None
    point_in_time_eligible: bool = False
    source: str = "SUSEP_SES_DERIVED"


def derive_susep_solvency_ratio(
    table: pd.DataFrame,
    *,
    susep_company_code: str,
    fiscal_year: int,
) -> InsuranceCapitalMetrics:
    """Derive year-end PLA/CMR from exact `Ses_pl_margem.csv` fields.

    The annual structural observation is the December prudential snapshot. Exactly one
    row must exist for the official SUSEP company code and YYYY12 reference period.
    Duplicate, missing, nonnumeric, non-positive CMR or negative PLA evidence fails
    closed rather than being repaired or inferred.
    """

    _require_columns(table)
    code = _numeric_company_code(susep_company_code)
    reference_period = fiscal_year * 100 + 12

    company_codes = pd.to_numeric(table["coenti"], errors="coerce")
    periods = pd.to_numeric(table["damesano"], errors="coerce")
    selected = table.loc[
        (company_codes == code) & (periods == reference_period), list(_REQUIRED_COLUMNS)
    ].copy()
    if len(selected) != 1:
        return _unknown(susep_company_code, fiscal_year, reference_period)

    pla = pd.to_numeric(selected["plajustado"], errors="coerce").iloc[0]
    cmr = pd.to_numeric(selected["CMR"], errors="coerce").iloc[0]
    if pd.isna(pla) or pd.isna(cmr):
        return _unknown(susep_company_code, fiscal_year, reference_period)

    adjusted_equity = float(pla)
    capital_minimum_required = float(cmr)
    if (
        not isfinite(adjusted_equity)
        or not isfinite(capital_minimum_required)
        or adjusted_equity < 0.0
        or capital_minimum_required <= 0.0
    ):
        return _unknown(susep_company_code, fiscal_year, reference_period)

    solvency_ratio = adjusted_equity / capital_minimum_required
    capital_surplus = adjusted_equity - capital_minimum_required
    return InsuranceCapitalMetrics(
        susep_company_code=susep_company_code,
        fiscal_year=fiscal_year,
        reference_period=reference_period,
        adjusted_equity=adjusted_equity,
        capital_minimum_required=capital_minimum_required,
        capital_surplus=capital_surplus,
        solvency_ratio=solvency_ratio if isfinite(solvency_ratio) else None,
    )


def insurance_capital_features(
    table: pd.DataFrame,
    *,
    susep_company_code: str,
    fiscal_year: int,
) -> dict[str, float | None]:
    """Return the independently verified score-facing insurer capital feature."""

    metrics = derive_susep_solvency_ratio(
        table,
        susep_company_code=susep_company_code,
        fiscal_year=fiscal_year,
    )
    return {"solvency_ratio": metrics.solvency_ratio}


def _require_columns(table: pd.DataFrame) -> None:
    missing = [column for column in _REQUIRED_COLUMNS if column not in table.columns]
    if missing:
        raise ValueError(f"missing required SUSEP SES columns: {', '.join(missing)}")


def _numeric_company_code(value: str) -> int:
    stripped = value.strip()
    if not stripped or not stripped.isdigit():
        raise ValueError("susep_company_code must contain only digits")
    return int(stripped)


def _unknown(
    susep_company_code: str,
    fiscal_year: int,
    reference_period: int,
) -> InsuranceCapitalMetrics:
    return InsuranceCapitalMetrics(
        susep_company_code=susep_company_code,
        fiscal_year=fiscal_year,
        reference_period=reference_period,
        adjusted_equity=None,
        capital_minimum_required=None,
        capital_surplus=None,
        solvency_ratio=None,
    )
