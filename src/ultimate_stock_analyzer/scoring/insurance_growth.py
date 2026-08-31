from __future__ import annotations

from dataclasses import dataclass
from math import isfinite

import pandas as pd

_REQUIRED_COLUMNS = ("damesano", "coenti", "premio_ganho")


@dataclass(frozen=True, slots=True)
class InsuranceGrowthMetrics:
    """Strict five-year insurer premium growth derived from official SUSEP SES data."""

    susep_company_code: str
    fiscal_year: int
    start_year: int
    start_earned_premiums: float | None
    end_earned_premiums: float | None
    premiums_cagr_5y: float | None
    complete_history: bool
    point_in_time_eligible: bool = False
    source: str = "SUSEP_SES_DERIVED"


def derive_susep_premiums_cagr_5y(
    table: pd.DataFrame,
    *,
    susep_company_code: str,
    fiscal_year: int,
) -> InsuranceGrowthMetrics:
    """Derive strict five-year earned-premium CAGR from six consecutive full years.

    Each year must contain all twelve monthly reference periods for the exact numeric
    SUSEP company identifier. The contract starts at FY2014 to avoid mixing the older
    pre-December-2013 earned-premium definition. No interpolation is allowed.
    """

    _require_columns(table)
    code = _numeric_company_code(susep_company_code)
    start_year = fiscal_year - 5
    if start_year < 2014:
        return _unknown(susep_company_code, fiscal_year, start_year)

    periods = pd.to_numeric(table["damesano"], errors="coerce")
    company_codes = pd.to_numeric(table["coenti"], errors="coerce")
    premiums = pd.to_numeric(table["premio_ganho"], errors="coerce")

    annual: dict[int, float] = {}
    for year in range(start_year, fiscal_year + 1):
        year_mask = (company_codes == code) & ((periods // 100) == year)
        selected_periods = periods.loc[year_mask]
        selected_premiums = premiums.loc[year_mask]
        if selected_periods.empty or selected_premiums.empty:
            return _unknown(susep_company_code, fiscal_year, start_year)
        if selected_periods.isna().any() or selected_premiums.isna().any():
            return _unknown(susep_company_code, fiscal_year, start_year)

        months = {int(value) for value in selected_periods.tolist()}
        expected_months = {year * 100 + month for month in range(1, 13)}
        if months != expected_months:
            return _unknown(susep_company_code, fiscal_year, start_year)

        annual_total = float(selected_premiums.sum())
        if not isfinite(annual_total) or annual_total <= 0.0:
            return _unknown(susep_company_code, fiscal_year, start_year)
        annual[year] = annual_total

    start_value = annual[start_year]
    end_value = annual[fiscal_year]
    cagr = (end_value / start_value) ** (1.0 / 5.0) - 1.0
    if not isfinite(cagr):
        cagr = None

    return InsuranceGrowthMetrics(
        susep_company_code=susep_company_code,
        fiscal_year=fiscal_year,
        start_year=start_year,
        start_earned_premiums=start_value,
        end_earned_premiums=end_value,
        premiums_cagr_5y=cagr,
        complete_history=True,
    )


def insurance_growth_features(
    table: pd.DataFrame,
    *,
    susep_company_code: str,
    fiscal_year: int,
) -> dict[str, float | None]:
    metrics = derive_susep_premiums_cagr_5y(
        table,
        susep_company_code=susep_company_code,
        fiscal_year=fiscal_year,
    )
    return {"premiums_cagr_5y": metrics.premiums_cagr_5y}


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
    start_year: int,
) -> InsuranceGrowthMetrics:
    return InsuranceGrowthMetrics(
        susep_company_code=susep_company_code,
        fiscal_year=fiscal_year,
        start_year=start_year,
        start_earned_premiums=None,
        end_earned_premiums=None,
        premiums_cagr_5y=None,
        complete_history=False,
    )
