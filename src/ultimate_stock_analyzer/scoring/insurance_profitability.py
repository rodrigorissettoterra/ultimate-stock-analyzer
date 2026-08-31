from __future__ import annotations

from dataclasses import dataclass
from math import isfinite

import pandas as pd

_REQUIRED_COLUMNS = ("coenti", "damesano", "cmpid", "valor")
_NET_INCOME_CMPID = 518
_TOTAL_ASSETS_CMPID = 1039
_EQUITY_CMPID = 3333
_CURRENT_ACCOUNTING_ERA_START = 2014


@dataclass(frozen=True, slots=True)
class InsuranceProfitabilityMetrics:
    """Strict insurer profitability evidence derived from official SUSEP accounting fields."""

    susep_company_code: str
    fiscal_year: int
    net_income: float | None
    current_equity: float | None
    prior_equity: float | None
    current_total_assets: float | None
    prior_total_assets: float | None
    roe: float | None
    roa: float | None
    point_in_time_eligible: bool = False
    source: str = "SUSEP_SES_DERIVED"


def derive_susep_profitability_metrics(
    table: pd.DataFrame,
    *,
    susep_company_code: str,
    fiscal_year: int,
) -> InsuranceProfitabilityMetrics:
    """Derive year-end insurer ROE and ROA from exact SUSEP CMPIDs.

    Annual net income is the December YTD observation, never a sum of monthly
    cumulative observations. Balance-sheet fields are point-in-time values: ROE and
    ROA use average current/prior December snapshots. Missing, duplicate or nonnumeric
    evidence fails closed.
    """

    _require_columns(table)
    code = _numeric_company_code(susep_company_code)
    if fiscal_year < _CURRENT_ACCOUNTING_ERA_START:
        return _unknown(susep_company_code, fiscal_year)

    current_period = fiscal_year * 100 + 12
    prior_period = (fiscal_year - 1) * 100 + 12
    net_income = _exact_value(
        table, company_code=code, period=current_period, cmpid=_NET_INCOME_CMPID
    )
    current_equity = _exact_value(
        table, company_code=code, period=current_period, cmpid=_EQUITY_CMPID
    )
    prior_equity = _exact_value(
        table, company_code=code, period=prior_period, cmpid=_EQUITY_CMPID
    )
    current_assets = _exact_value(
        table, company_code=code, period=current_period, cmpid=_TOTAL_ASSETS_CMPID
    )
    prior_assets = _exact_value(
        table, company_code=code, period=prior_period, cmpid=_TOTAL_ASSETS_CMPID
    )

    return InsuranceProfitabilityMetrics(
        susep_company_code=susep_company_code,
        fiscal_year=fiscal_year,
        net_income=net_income,
        current_equity=current_equity,
        prior_equity=prior_equity,
        current_total_assets=current_assets,
        prior_total_assets=prior_assets,
        roe=_return_on_average_balance(net_income, prior_equity, current_equity),
        roa=_return_on_average_balance(net_income, prior_assets, current_assets),
    )


def insurance_profitability_features(
    table: pd.DataFrame,
    *,
    susep_company_code: str,
    fiscal_year: int,
) -> dict[str, float | None]:
    """Return verified score-facing insurer profitability features."""

    metrics = derive_susep_profitability_metrics(
        table, susep_company_code=susep_company_code, fiscal_year=fiscal_year
    )
    return {"roe": metrics.roe, "roa": metrics.roa}


def _require_columns(table: pd.DataFrame) -> None:
    missing = [column for column in _REQUIRED_COLUMNS if column not in table.columns]
    if missing:
        raise ValueError(f"missing required SUSEP SES columns: {', '.join(missing)}")


def _numeric_company_code(value: str) -> int:
    stripped = value.strip()
    if not stripped or not stripped.isdigit():
        raise ValueError("susep_company_code must contain only digits")
    return int(stripped)


def _exact_value(
    table: pd.DataFrame,
    *,
    company_code: int,
    period: int,
    cmpid: int,
) -> float | None:
    company_codes = pd.to_numeric(table["coenti"], errors="coerce")
    periods = pd.to_numeric(table["damesano"], errors="coerce")
    item_ids = pd.to_numeric(table["cmpid"], errors="coerce")
    selected = table.loc[
        (company_codes == company_code) & (periods == period) & (item_ids == cmpid),
        "valor",
    ]
    if len(selected) != 1:
        return None
    numeric = pd.to_numeric(selected, errors="coerce").iloc[0]
    if pd.isna(numeric):
        return None
    value = float(numeric)
    return value if isfinite(value) else None


def _return_on_average_balance(
    net_income: float | None,
    beginning_balance: float | None,
    ending_balance: float | None,
) -> float | None:
    if net_income is None or beginning_balance is None or ending_balance is None:
        return None
    if not all(isfinite(value) for value in (net_income, beginning_balance, ending_balance)):
        return None
    average_balance = (beginning_balance + ending_balance) / 2.0
    if average_balance <= 0.0:
        return None
    result = net_income / average_balance
    return result if isfinite(result) else None


def _unknown(susep_company_code: str, fiscal_year: int) -> InsuranceProfitabilityMetrics:
    return InsuranceProfitabilityMetrics(
        susep_company_code=susep_company_code,
        fiscal_year=fiscal_year,
        net_income=None,
        current_equity=None,
        prior_equity=None,
        current_total_assets=None,
        prior_total_assets=None,
        roe=None,
        roa=None,
    )
