from __future__ import annotations

from dataclasses import dataclass
from math import isfinite

import pandas as pd

_REQUIRED_COLUMNS = ("coenti", "damesano", "cmpid", "valor")
_NET_INCOME_CMPID = 518
_CURRENT_ACCOUNTING_ERA_START = 2014


@dataclass(frozen=True, slots=True)
class InsuranceNetIncomeGrowthMetrics:
    """Strict five-year insurer net-income growth from official SUSEP accounting data."""

    susep_company_code: str
    fiscal_year: int
    start_year: int
    start_net_income: float | None
    end_net_income: float | None
    net_income_cagr_5y: float | None
    complete_history: bool
    point_in_time_eligible: bool = False
    source: str = "SUSEP_SES_DERIVED"


def derive_susep_net_income_cagr_5y(
    table: pd.DataFrame,
    *,
    susep_company_code: str,
    fiscal_year: int,
) -> InsuranceNetIncomeGrowthMetrics:
    """Derive strict five-year net-income CAGR from six consecutive December YTD values.

    CMPID 518 is the official SUSEP net-income line confirmed by the current
    `Ses_campos.csv` dictionary. The annual observation is December YTD and is never
    reconstructed by summing monthly cumulative P&L rows. All six consecutive fiscal
    years must have exactly one numeric December observation for the exact SUSEP
    company code. CAGR is defined only when both endpoint profits are strictly positive;
    zero or negative endpoints remain UNKNOWN rather than applying a sign-changing
    transformation with ambiguous economic meaning.
    """

    _require_columns(table)
    code = _numeric_company_code(susep_company_code)
    start_year = fiscal_year - 5
    if start_year < _CURRENT_ACCOUNTING_ERA_START:
        return _unknown(susep_company_code, fiscal_year, start_year)

    annual: dict[int, float] = {}
    for year in range(start_year, fiscal_year + 1):
        value = _exact_december_net_income(table, company_code=code, fiscal_year=year)
        if value is None:
            return _unknown(susep_company_code, fiscal_year, start_year)
        annual[year] = value

    start_value = annual[start_year]
    end_value = annual[fiscal_year]
    if start_value <= 0.0 or end_value <= 0.0:
        return InsuranceNetIncomeGrowthMetrics(
            susep_company_code=susep_company_code,
            fiscal_year=fiscal_year,
            start_year=start_year,
            start_net_income=start_value,
            end_net_income=end_value,
            net_income_cagr_5y=None,
            complete_history=True,
        )

    cagr = (end_value / start_value) ** (1.0 / 5.0) - 1.0
    return InsuranceNetIncomeGrowthMetrics(
        susep_company_code=susep_company_code,
        fiscal_year=fiscal_year,
        start_year=start_year,
        start_net_income=start_value,
        end_net_income=end_value,
        net_income_cagr_5y=cagr if isfinite(cagr) else None,
        complete_history=True,
    )


def insurance_net_income_growth_features(
    table: pd.DataFrame,
    *,
    susep_company_code: str,
    fiscal_year: int,
) -> dict[str, float | None]:
    metrics = derive_susep_net_income_cagr_5y(
        table,
        susep_company_code=susep_company_code,
        fiscal_year=fiscal_year,
    )
    return {"net_income_cagr_5y": metrics.net_income_cagr_5y}


def _require_columns(table: pd.DataFrame) -> None:
    missing = [column for column in _REQUIRED_COLUMNS if column not in table.columns]
    if missing:
        raise ValueError(f"missing required SUSEP SES columns: {', '.join(missing)}")


def _numeric_company_code(value: str) -> int:
    stripped = value.strip()
    if not stripped or not stripped.isdigit():
        raise ValueError("susep_company_code must contain only digits")
    return int(stripped)


def _exact_december_net_income(
    table: pd.DataFrame,
    *,
    company_code: int,
    fiscal_year: int,
) -> float | None:
    company_codes = pd.to_numeric(table["coenti"], errors="coerce")
    periods = pd.to_numeric(table["damesano"], errors="coerce")
    item_ids = pd.to_numeric(table["cmpid"], errors="coerce")
    period = fiscal_year * 100 + 12
    selected = table.loc[
        (company_codes == company_code)
        & (periods == period)
        & (item_ids == _NET_INCOME_CMPID),
        "valor",
    ]
    if len(selected) != 1:
        return None
    numeric = pd.to_numeric(selected, errors="coerce").iloc[0]
    if pd.isna(numeric):
        return None
    value = float(numeric)
    return value if isfinite(value) else None


def _unknown(
    susep_company_code: str,
    fiscal_year: int,
    start_year: int,
) -> InsuranceNetIncomeGrowthMetrics:
    return InsuranceNetIncomeGrowthMetrics(
        susep_company_code=susep_company_code,
        fiscal_year=fiscal_year,
        start_year=start_year,
        start_net_income=None,
        end_net_income=None,
        net_income_cagr_5y=None,
        complete_history=False,
    )
