from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Iterable

from ultimate_stock_analyzer.domain.master import BankPrudentialAnnualRecord


@dataclass(frozen=True, slots=True)
class BankGrowthMetrics:
    """Deterministic five-year bank growth features derived from IFData profiles.

    The feature contract is deliberately strict: a valid observation requires six
    consecutive annual profiles (target year and the five preceding fiscal years),
    stable prudential-conglomerate identity, and complete source values. Derived
    metrics inherit IFData's non-PIT limitation and therefore remain ineligible for
    strict point-in-time backtests.
    """

    company_id: str
    fiscal_year: int
    start_year: int
    end_year: int
    ifdata_cod_inst: str
    net_income_cagr_5y: float | None
    loan_cagr_5y: float | None
    point_in_time_eligible: bool = False
    source: str = "BCB_IFDATA_DERIVED"


def derive_bank_growth_metrics(
    profiles: Iterable[BankPrudentialAnnualRecord],
    *,
    company_id: str,
    fiscal_year: int,
) -> BankGrowthMetrics:
    """Derive five-year CAGR features using exact fiscal-year endpoints.

    ``5y`` means an endpoint distance of exactly five fiscal years, e.g. FY2020 to
    FY2025, with exponent ``1 / 5``. Six consecutive annual profiles are required so
    a sparse historical download cannot silently satisfy the growth contract.
    Ordinary CAGR is undefined for non-positive endpoints; those metrics fail closed
    to ``None`` rather than applying a signed or absolute-value convention.
    """

    start_year = fiscal_year - 5
    required_years = tuple(range(start_year, fiscal_year + 1))
    by_year: dict[int, BankPrudentialAnnualRecord] = {}

    for profile in profiles:
        if profile.company_id != company_id:
            continue
        if profile.fiscal_year in by_year:
            raise ValueError(
                "duplicate IFData bank profile for "
                f"{company_id}/{profile.fiscal_year}"
            )
        by_year[profile.fiscal_year] = profile

    available = [by_year.get(year) for year in required_years]
    complete = all(profile is not None for profile in available)
    if not complete:
        return BankGrowthMetrics(
            company_id=company_id,
            fiscal_year=fiscal_year,
            start_year=start_year,
            end_year=fiscal_year,
            ifdata_cod_inst=_latest_cod_inst(by_year, fiscal_year),
            net_income_cagr_5y=None,
            loan_cagr_5y=None,
        )

    history = [profile for profile in available if profile is not None]
    cod_inst = history[-1].ifdata_cod_inst
    if any(profile.ifdata_cod_inst != cod_inst for profile in history):
        return BankGrowthMetrics(
            company_id=company_id,
            fiscal_year=fiscal_year,
            start_year=start_year,
            end_year=fiscal_year,
            ifdata_cod_inst=cod_inst,
            net_income_cagr_5y=None,
            loan_cagr_5y=None,
        )

    net_income_values = [profile.annual_net_income for profile in history]
    loan_values = [profile.gross_credit_portfolio for profile in history]

    return BankGrowthMetrics(
        company_id=company_id,
        fiscal_year=fiscal_year,
        start_year=start_year,
        end_year=fiscal_year,
        ifdata_cod_inst=cod_inst,
        net_income_cagr_5y=_strict_cagr(net_income_values, periods=5),
        loan_cagr_5y=_strict_cagr(loan_values, periods=5),
    )


def bank_growth_features(
    profiles: Iterable[BankPrudentialAnnualRecord],
    *,
    company_id: str,
    fiscal_year: int,
) -> dict[str, float | None]:
    """Return scoring-compatible feature names for the bank growth category."""

    metrics = derive_bank_growth_metrics(
        profiles,
        company_id=company_id,
        fiscal_year=fiscal_year,
    )
    return {
        "loan_cagr_5y": metrics.loan_cagr_5y,
        "net_income_cagr_5y": metrics.net_income_cagr_5y,
    }


def _strict_cagr(values: list[float | None], *, periods: int) -> float | None:
    if len(values) != periods + 1 or any(value is None for value in values):
        return None
    start = float(values[0])  # type: ignore[arg-type]
    end = float(values[-1])  # type: ignore[arg-type]
    if not isfinite(start) or not isfinite(end) or start <= 0.0 or end <= 0.0:
        return None
    result = (end / start) ** (1.0 / periods) - 1.0
    return result if isfinite(result) else None


def _latest_cod_inst(
    by_year: dict[int, BankPrudentialAnnualRecord], fiscal_year: int
) -> str:
    latest = by_year.get(fiscal_year)
    return latest.ifdata_cod_inst if latest is not None else ""
