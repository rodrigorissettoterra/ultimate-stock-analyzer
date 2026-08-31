from __future__ import annotations

from dataclasses import dataclass
from math import isfinite

import pandas as pd

_REQUIRED_COLUMNS = (
    "damesano",
    "coenti",
    "premio_ganho",
    "sinistro_ocorrido",
)
_CURRENT_SINISTRALIDADE_ERA_START = 201312


@dataclass(frozen=True, slots=True)
class InsuranceUnderwritingMetrics:
    """Verified current-era SUSEP underwriting evidence for one supervised insurer.

    SUSEP states that, from December 2013, earned premium is gross of reinsurance and
    sinistralidade is measured using incurred claims. Current SES downloads are not
    revision-aware, so derived values remain ineligible for strict PIT backtests.
    """

    susep_company_code: str
    fiscal_year: int
    annual_earned_premiums: float | None
    annual_incurred_claims: float | None
    loss_ratio: float | None
    complete_months: bool
    point_in_time_eligible: bool = False
    source: str = "SUSEP_SES_DERIVED"


def derive_susep_loss_ratio(
    table: pd.DataFrame,
    *,
    susep_company_code: str,
    fiscal_year: int,
) -> InsuranceUnderwritingMetrics:
    """Derive annual insurer loss ratio from exact official SES columns.

    The current contract intentionally starts in FY2014 so a fiscal year never mixes
    the pre-December-2013 and current SUSEP definitions. A valid annual observation
    requires all twelve monthly periods for the exact SUSEP company identifier and
    complete numeric ``premio_ganho`` / ``sinistro_ocorrido`` values. Missing or
    invalid evidence fails closed to ``None``.
    """

    _require_columns(table)
    code = _numeric_company_code(susep_company_code)
    if fiscal_year < 2014:
        return _unknown(susep_company_code, fiscal_year)

    periods = pd.to_numeric(table["damesano"], errors="coerce")
    company_codes = pd.to_numeric(table["coenti"], errors="coerce")
    mask = (company_codes == code) & ((periods // 100) == fiscal_year)
    selected = table.loc[mask, list(_REQUIRED_COLUMNS)].copy()
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
    claims = pd.to_numeric(selected["sinistro_ocorrido"], errors="coerce")
    if earned.isna().any() or claims.isna().any():
        return _unknown(susep_company_code, fiscal_year, complete_months=True)

    annual_earned = float(earned.sum())
    annual_claims = float(claims.sum())
    ratio = _strict_loss_ratio(annual_claims, annual_earned)
    return InsuranceUnderwritingMetrics(
        susep_company_code=susep_company_code,
        fiscal_year=fiscal_year,
        annual_earned_premiums=annual_earned if isfinite(annual_earned) else None,
        annual_incurred_claims=annual_claims if isfinite(annual_claims) else None,
        loss_ratio=ratio,
        complete_months=True,
    )


def insurance_underwriting_features(
    table: pd.DataFrame,
    *,
    susep_company_code: str,
    fiscal_year: int,
) -> dict[str, float | None]:
    """Return scoring-compatible verified insurer underwriting features."""

    metrics = derive_susep_loss_ratio(
        table,
        susep_company_code=susep_company_code,
        fiscal_year=fiscal_year,
    )
    return {"loss_ratio": metrics.loss_ratio}


def _require_columns(table: pd.DataFrame) -> None:
    missing = [column for column in _REQUIRED_COLUMNS if column not in table.columns]
    if missing:
        raise ValueError(f"missing required SUSEP SES columns: {', '.join(missing)}")


def _numeric_company_code(value: str) -> int:
    stripped = value.strip()
    if not stripped or not stripped.isdigit():
        raise ValueError("susep_company_code must contain only digits")
    return int(stripped)


def _strict_loss_ratio(claims: float, earned_premiums: float) -> float | None:
    if not isfinite(claims) or not isfinite(earned_premiums):
        return None
    if claims < 0.0 or earned_premiums <= 0.0:
        return None
    result = claims / earned_premiums
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
        loss_ratio=None,
        complete_months=complete_months,
    )
