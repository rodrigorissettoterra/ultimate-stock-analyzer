from __future__ import annotations

import math
from collections.abc import Sequence


def safe_div(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or denominator is None or denominator == 0:
        return None
    return numerator / denominator


def average(*values: float | None) -> float | None:
    valid = [v for v in values if v is not None]
    return sum(valid) / len(valid) if valid else None


def cagr(start: float | None, end: float | None, years: float) -> float | None:
    if start is None or end is None or years <= 0 or start <= 0 or end < 0:
        return None
    return (end / start) ** (1 / years) - 1


def gross_margin(gross_profit: float | None, revenue: float | None) -> float | None:
    return safe_div(gross_profit, revenue)


def ebit_margin(ebit: float | None, revenue: float | None) -> float | None:
    return safe_div(ebit, revenue)


def net_margin(net_income: float | None, revenue: float | None) -> float | None:
    return safe_div(net_income, revenue)


def roe(net_income: float | None, equity_begin: float | None, equity_end: float | None) -> float | None:
    return safe_div(net_income, average(equity_begin, equity_end))


def roic(
    ebit: float | None,
    effective_tax_rate: float | None,
    invested_capital_begin: float | None,
    invested_capital_end: float | None,
) -> float | None:
    if ebit is None or effective_tax_rate is None:
        return None
    nopat = ebit * (1 - effective_tax_rate)
    return safe_div(nopat, average(invested_capital_begin, invested_capital_end))


def net_debt(gross_debt: float | None, cash: float | None) -> float | None:
    if gross_debt is None or cash is None:
        return None
    return gross_debt - cash


def net_debt_to_ebitda(
    gross_debt: float | None, cash: float | None, ebitda: float | None
) -> float | None:
    nd = net_debt(gross_debt, cash)
    return safe_div(nd, ebitda)


def interest_coverage(ebit: float | None, interest_expense: float | None) -> float | None:
    if interest_expense is None:
        return None
    return safe_div(ebit, abs(interest_expense))


def free_cash_flow(cash_from_operations: float | None, capex: float | None) -> float | None:
    if cash_from_operations is None or capex is None:
        return None
    return cash_from_operations - abs(capex)


def cash_conversion(cash_from_operations: float | None, net_income: float | None) -> float | None:
    return safe_div(cash_from_operations, net_income)


def fcf_yield(fcf: float | None, market_cap: float | None) -> float | None:
    return safe_div(fcf, market_cap)


def payout_ratio(dividends_and_jcp: float | None, net_income: float | None) -> float | None:
    return safe_div(dividends_and_jcp, net_income)


def fcf_payout(dividends_and_jcp: float | None, fcf: float | None) -> float | None:
    return safe_div(dividends_and_jcp, fcf)


def debt_to_equity(gross_debt: float | None, equity: float | None) -> float | None:
    return safe_div(gross_debt, equity)


def coefficient_of_variation(values: Sequence[float]) -> float | None:
    vals = [float(v) for v in values if math.isfinite(float(v))]
    if len(vals) < 2:
        return None
    mean = sum(vals) / len(vals)
    if mean == 0:
        return None
    variance = sum((v - mean) ** 2 for v in vals) / (len(vals) - 1)
    return math.sqrt(variance) / abs(mean)
