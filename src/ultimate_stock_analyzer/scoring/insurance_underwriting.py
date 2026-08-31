from __future__ import annotations

from dataclasses import dataclass
from math import isfinite

import pandas as pd

_BASE_REQUIRED_COLUMNS = ("damesano", "coenti", "premio_ganho")
_LOSS_COLUMN = "sinistro_ocorrido"
_COMMERCIAL_EXPENSE_COLUMN = "desp_com"
_CURRENT_SINISTRALIDADE_ERA_START = 201312


@dataclass(frozen=True, slots=True)
class InsuranceUnderwritingMetrics:
    """Verified current-era SUSEP underwriting evidence for one supervised insurer.

    SUSEP states that, from December 2013, earned premium is gross of reinsurance and
    sinistralidade is measured using incurred claims. SUSEP also publishes the
    commercial-expense index as commercial expenses divided by earned premium.
    Current SES downloads are not revision-aware, so derived values remain ineligible
    for strict PIT backtests.
    """

    susep_company_code: str
    fiscal_year: int
    annual_earned_premiums: float | None
    annual_incurred_claims: float | None
    annual_commercial_expenses: float | None
    loss_ratio: float | None
    commercial_expense_ratio: float | None
    complete_months: bool
    point_in_time_eligible: bool = False
    source: str = "SUSEP_SES_DERIVED"


def derive_susep_underwriting_metrics(
    table: pd.DataFrame,
    *,
    susep_company_code: str,
    fiscal_year: int,
) -> InsuranceUnderwritingMetrics:
    """Derive independently verified annual underwriting ratios from exact SES fields.

    Identity, period and earned premium are common evidence. The incurred-claims and
    commercial-expense numerators are deliberately independent: absence or corruption
    of one optional source field must not make the other verified metric unavailable.
    A valid annual denominator requires all twelve monthly periods for the exact SUSEP
    company identifier. Metric-specific missing or invalid evidence fails only that
    metric closed to ``None``.
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
    if not isfinite(annual_earned):
        annual_earned_value = None
    else:
        annual_earned_value = annual_earned

    annual_claims = _optional_annual_sum(selected, _LOSS_COLUMN)
    annual_commercial = _optional_annual_sum(selected, _COMMERCIAL_EXPENSE_COLUMN)

    return InsuranceUnderwritingMetrics(
        susep_company_code=susep_company_code,
        fiscal_year=fiscal_year,
        annual_earned_premiums=annual_earned_value,
        annual_incurred_claims=annual_claims,
        annual_commercial_expenses=annual_commercial,
        loss_ratio=(
            _strict_ratio(annual_claims, annual_earned)
            if annual_claims is not None
            else None
        ),
        commercial_expense_ratio=(
            _strict_ratio(annual_commercial, annual_earned)
            if annual_commercial is not None
            else None
        ),
        complete_months=True,
    )


def derive_susep_loss_ratio(
    table: pd.DataFrame,
    *,
    susep_company_code: str,
    fiscal_year: int,
) -> InsuranceUnderwritingMetrics:
    """Backward-compatible entry point for verified underwriting metrics."""

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
) -> dict[str, float | None]:
    """Return scoring-compatible verified insurer underwriting features.

    ``commercial_expense_ratio`` is deliberately not mapped to the model's generic
    ``expense_ratio``: SUSEP's expense/combined-ratio methodology requires additional
    components beyond commercial expenses alone.
    """

    metrics = derive_susep_underwriting_metrics(
        table,
        susep_company_code=susep_company_code,
        fiscal_year=fiscal_year,
    )
    return {"loss_ratio": metrics.loss_ratio}


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
        loss_ratio=None,
        commercial_expense_ratio=None,
        complete_months=complete_months,
    )
