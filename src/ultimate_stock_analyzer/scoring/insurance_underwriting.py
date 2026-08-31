from __future__ import annotations

from dataclasses import dataclass
from math import isfinite

import pandas as pd

_BASE_REQUIRED_COLUMNS = ("damesano", "coenti", "premio_ganho")
_LOSS_COLUMN = "sinistro_ocorrido"
_COMMERCIAL_EXPENSE_COLUMN = "desp_com"
_ADMINISTRATIVE_EXPENSE_CMPID = 4069
_CURRENT_SINISTRALIDADE_ERA_START = 201312


@dataclass(frozen=True, slots=True)
class InsuranceUnderwritingMetrics:
    """Verified current-era SUSEP underwriting evidence for one supervised insurer.

    SUSEP states that, from December 2013, earned premium is gross of reinsurance and
    sinistralidade is measured using incurred claims. The regulator separately reports
    commercial and administrative expense indices and the combined ratio. Current SES
    downloads are not revision-aware, so derived values remain ineligible for strict
    point-in-time backtests.
    """

    susep_company_code: str
    fiscal_year: int
    annual_earned_premiums: float | None
    annual_incurred_claims: float | None
    annual_commercial_expenses: float | None
    annual_administrative_expenses: float | None
    loss_ratio: float | None
    commercial_expense_ratio: float | None
    administrative_expense_ratio: float | None
    expense_ratio: float | None
    combined_ratio: float | None
    complete_months: bool
    point_in_time_eligible: bool = False
    source: str = "SUSEP_SES_DERIVED"


def derive_susep_underwriting_metrics(
    table: pd.DataFrame,
    *,
    susep_company_code: str,
    fiscal_year: int,
    accounting_table: pd.DataFrame | None = None,
) -> InsuranceUnderwritingMetrics:
    """Derive independently verified annual underwriting ratios from exact SUSEP fields.

    ``table`` is `Ses_seguros.csv`: annual earned premiums, incurred claims and
    commercial expenses are sums of complete monthly operating observations.

    ``accounting_table`` is `SES_Balanco.csv`. Administrative expense is the exact
    December YTD DRE observation for current CMPID 4069, whose official dictionary
    description is ``(-) DESPESAS ADMINISTRATIVAS``. Because the accounting line is
    explicitly negative-signed, only a finite non-positive source value is normalized
    to a positive expense magnitude. A positive source value fails closed instead of
    being converted with ``abs``.

    Metric dependencies are independent: missing claims must not suppress expense
    ratios, and missing administrative/commercial expenses must not suppress the
    already-verified loss ratio.
    """

    _require_base_columns(table)
    code = _numeric_company_code(susep_company_code)
    if fiscal_year < 2014:
        return _unknown(susep_company_code, fiscal_year)

    periods = pd.to_numeric(table["damesano"], errors="coerce")
    company_codes = pd.to_numeric(table["coenti"], errors="coerce")
    mask = (company_codes == code) & ((periods // 100) == fiscal_year)
    selected_columns = list(_BASE_REQUIRED_COLUMNS)
    if _LOSS_COLUMN in table.columns:
        selected_columns.append(_LOSS_COLUMN)
    if _COMMERCIAL_EXPENSE_COLUMN in table.columns:
        selected_columns.append(_COMMERCIAL_EXPENSE_COLUMN)
    selected = table.loc[mask, selected_columns].copy()
    if selected.empty:
        return _unknown(susep_company_code, fiscal_year)

    selected_periods = pd.to_numeric(selected["damesano"], errors="coerce")
    if selected_periods.isna().any():
        return _unknown(susep_company_code, fiscal_year)
    months = {int(value) for value in selected_periods.tolist()}
    expected_months = {fiscal_year * 100 + month for month in range(1, 13)}
    if months != expected_months:
        return _unknown(susep_company_code, fiscal_year)

    earned = pd.to_numeric(selected["premio_ganho"], errors="coerce")
    if earned.isna().any():
        return _unknown(susep_company_code, fiscal_year, complete_months=True)
    annual_earned = float(earned.sum())
    annual_earned_value = annual_earned if isfinite(annual_earned) else None

    annual_claims = _optional_annual_sum(selected, _LOSS_COLUMN)
    annual_commercial = _optional_annual_sum(selected, _COMMERCIAL_EXPENSE_COLUMN)
    annual_administrative = (
        _administrative_expense_from_accounting(
            accounting_table,
            company_code=code,
            fiscal_year=fiscal_year,
        )
        if accounting_table is not None
        else None
    )

    loss_ratio = (
        _strict_ratio(annual_claims, annual_earned)
        if annual_claims is not None
        else None
    )
    commercial_ratio = (
        _strict_ratio(annual_commercial, annual_earned)
        if annual_commercial is not None
        else None
    )
    administrative_ratio = (
        _strict_ratio(annual_administrative, annual_earned)
        if annual_administrative is not None
        else None
    )
    expense_ratio = (
        _strict_ratio(annual_commercial + annual_administrative, annual_earned)
        if annual_commercial is not None and annual_administrative is not None
        else None
    )
    combined_ratio = (
        _strict_ratio(
            annual_claims + annual_commercial + annual_administrative,
            annual_earned,
        )
        if annual_claims is not None
        and annual_commercial is not None
        and annual_administrative is not None
        else None
    )

    return InsuranceUnderwritingMetrics(
        susep_company_code=susep_company_code,
        fiscal_year=fiscal_year,
        annual_earned_premiums=annual_earned_value,
        annual_incurred_claims=annual_claims,
        annual_commercial_expenses=annual_commercial,
        annual_administrative_expenses=annual_administrative,
        loss_ratio=loss_ratio,
        commercial_expense_ratio=commercial_ratio,
        administrative_expense_ratio=administrative_ratio,
        expense_ratio=expense_ratio,
        combined_ratio=combined_ratio,
        complete_months=True,
    )


def derive_susep_loss_ratio(
    table: pd.DataFrame,
    *,
    susep_company_code: str,
    fiscal_year: int,
) -> InsuranceUnderwritingMetrics:
    """Backward-compatible entry point for verified loss/commercial evidence."""

    return derive_susep_underwriting_metrics(
        table,
        susep_company_code=susep_company_code,
        fiscal_year=fiscal_year,
    )


def insurance_underwriting_features(
    table: pd.DataFrame,
    *,
    susep_company_code: str,
    fiscal_year: int,
    accounting_table: pd.DataFrame | None = None,
) -> dict[str, float | None]:
    """Return score-facing insurer underwriting metrics with verified semantics."""

    metrics = derive_susep_underwriting_metrics(
        table,
        susep_company_code=susep_company_code,
        fiscal_year=fiscal_year,
        accounting_table=accounting_table,
    )
    return {
        "combined_ratio": metrics.combined_ratio,
        "loss_ratio": metrics.loss_ratio,
        "expense_ratio": metrics.expense_ratio,
    }


def _require_base_columns(table: pd.DataFrame) -> None:
    missing = [column for column in _BASE_REQUIRED_COLUMNS if column not in table.columns]
    if missing:
        raise ValueError(f"missing required SUSEP SES columns: {', '.join(missing)}")


def _optional_annual_sum(table: pd.DataFrame, column: str) -> float | None:
    if column not in table.columns:
        return None
    values = pd.to_numeric(table[column], errors="coerce")
    if values.isna().any():
        return None
    annual = float(values.sum())
    return annual if isfinite(annual) else None


def _administrative_expense_from_accounting(
    table: pd.DataFrame,
    *,
    company_code: int,
    fiscal_year: int,
) -> float | None:
    required = ("coenti", "damesano", "cmpid", "valor")
    if any(column not in table.columns for column in required):
        return None

    company_codes = pd.to_numeric(table["coenti"], errors="coerce")
    periods = pd.to_numeric(table["damesano"], errors="coerce")
    item_ids = pd.to_numeric(table["cmpid"], errors="coerce")
    selected = table.loc[
        (company_codes == company_code)
        & (periods == fiscal_year * 100 + 12)
        & (item_ids == _ADMINISTRATIVE_EXPENSE_CMPID),
        "valor",
    ]
    if len(selected) != 1:
        return None

    numeric = pd.to_numeric(selected, errors="coerce").iloc[0]
    if pd.isna(numeric):
        return None
    signed_value = float(numeric)
    if not isfinite(signed_value) or signed_value > 0.0:
        return None
    return -signed_value


def _numeric_company_code(value: str) -> int:
    stripped = value.strip()
    if not stripped or not stripped.isdigit():
        raise ValueError("susep_company_code must contain only digits")
    return int(stripped)


def _strict_ratio(numerator: float, earned_premiums: float) -> float | None:
    if not isfinite(numerator) or not isfinite(earned_premiums):
        return None
    if numerator < 0.0 or earned_premiums <= 0.0:
        return None
    result = numerator / earned_premiums
    return result if isfinite(result) else None


def _unknown(
    susep_company_code: str,
    fiscal_year: int,
    *,
    complete_months: bool = False,
) -> InsuranceUnderwritingMetrics:
    return InsuranceUnderwritingMetrics(
        susep_company_code=susep_company_code,
        fiscal_year=fiscal_year,
        annual_earned_premiums=None,
        annual_incurred_claims=None,
        annual_commercial_expenses=None,
        annual_administrative_expenses=None,
        loss_ratio=None,
        commercial_expense_ratio=None,
        administrative_expense_ratio=None,
        expense_ratio=None,
        combined_ratio=None,
        complete_months=complete_months,
    )
