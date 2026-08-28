from __future__ import annotations

import math
from collections.abc import Sequence


def safe_div(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or denominator is None or denominator == 0:
        return None
    return numerator / denominator


def average(*values: float | None) -> float | None:
    valid = [value for value in values if value is not None]
    return sum(valid) / len(valid) if valid else None


def cagr(start: float | None, end: float | None, years: float) -> float | None:
    if start is None or end is None or years <= 0 or start <= 0 or end < 0:
        return None
    return (end / start) ** (1 / years) - 1


def yoy_growth(current: float | None, prior: float | None) -> float | None:
    if current is None or prior is None or prior == 0:
        return None
    return current / abs(prior) - 1


def gross_margin(gross_profit: float | None, revenue: float | None) -> float | None:
    return safe_div(gross_profit, revenue)


def ebit_margin(ebit: float | None, revenue: float | None) -> float | None:
    return safe_div(ebit, revenue)


def ebitda_margin(ebitda: float | None, revenue: float | None) -> float | None:
    return safe_div(ebitda, revenue)


def net_margin(net_income: float | None, revenue: float | None) -> float | None:
    return safe_div(net_income, revenue)


def cfo_margin(cash_from_operations: float | None, revenue: float | None) -> float | None:
    return safe_div(cash_from_operations, revenue)


def fcf_margin(fcf: float | None, revenue: float | None) -> float | None:
    return safe_div(fcf, revenue)


def roe(
    net_income: float | None,
    equity_begin: float | None,
    equity_end: float | None,
) -> float | None:
    return safe_div(net_income, average(equity_begin, equity_end))


def roa(
    net_income: float | None,
    assets_begin: float | None,
    assets_end: float | None,
) -> float | None:
    return safe_div(net_income, average(assets_begin, assets_end))


def nopat(ebit: float | None, effective_tax_rate: float | None) -> float | None:
    if ebit is None or effective_tax_rate is None:
        return None
    return ebit * (1 - effective_tax_rate)


def roic(
    ebit: float | None,
    effective_tax_rate: float | None,
    invested_capital_begin: float | None,
    invested_capital_end: float | None,
) -> float | None:
    return safe_div(
        nopat(ebit, effective_tax_rate),
        average(invested_capital_begin, invested_capital_end),
    )


def capital_employed(
    total_assets: float | None,
    current_liabilities: float | None,
) -> float | None:
    if total_assets is None or current_liabilities is None:
        return None
    return total_assets - current_liabilities


def roce(
    ebit: float | None,
    assets_begin: float | None,
    current_liabilities_begin: float | None,
    assets_end: float | None,
    current_liabilities_end: float | None,
) -> float | None:
    begin = capital_employed(assets_begin, current_liabilities_begin)
    end = capital_employed(assets_end, current_liabilities_end)
    return safe_div(ebit, average(begin, end))


def roic_spread(roic_value: float | None, wacc: float | None) -> float | None:
    if roic_value is None or wacc is None:
        return None
    return roic_value - wacc


def effective_tax_rate(
    tax_expense: float | None,
    pretax_income: float | None,
) -> float | None:
    if tax_expense is None or pretax_income is None or pretax_income <= 0:
        return None
    return abs(tax_expense) / pretax_income


def ebitda(
    ebit: float | None,
    depreciation_and_amortization: float | None,
) -> float | None:
    if ebit is None or depreciation_and_amortization is None:
        return None
    return ebit + abs(depreciation_and_amortization)


def gross_debt(
    current_borrowings: float | None,
    noncurrent_borrowings: float | None,
) -> float | None:
    if current_borrowings is None or noncurrent_borrowings is None:
        return None
    return current_borrowings + noncurrent_borrowings


def liquid_funds(
    cash_and_equivalents: float | None,
    current_financial_investments: float | None = None,
) -> float | None:
    if cash_and_equivalents is None:
        return None
    if current_financial_investments is None:
        return cash_and_equivalents
    return cash_and_equivalents + current_financial_investments


def net_debt(gross_debt: float | None, cash: float | None) -> float | None:
    if gross_debt is None or cash is None:
        return None
    return gross_debt - cash


def gross_debt_to_ebitda(
    gross_debt: float | None,
    ebitda: float | None,
) -> float | None:
    return safe_div(gross_debt, ebitda)


def net_debt_to_ebitda(
    gross_debt: float | None,
    cash: float | None,
    ebitda: float | None,
) -> float | None:
    return safe_div(net_debt(gross_debt, cash), ebitda)


def net_debt_to_fcf(
    gross_debt: float | None,
    cash: float | None,
    fcf: float | None,
) -> float | None:
    return safe_div(net_debt(gross_debt, cash), fcf)


def debt_to_equity(gross_debt: float | None, equity: float | None) -> float | None:
    return safe_div(gross_debt, equity)


def debt_to_assets(gross_debt: float | None, total_assets: float | None) -> float | None:
    return safe_div(gross_debt, total_assets)


def equity_ratio(equity: float | None, total_assets: float | None) -> float | None:
    return safe_div(equity, total_assets)


def financial_leverage(total_assets: float | None, equity: float | None) -> float | None:
    return safe_div(total_assets, equity)


def cash_to_debt(cash: float | None, gross_debt: float | None) -> float | None:
    return safe_div(cash, gross_debt)


def operating_cash_flow_to_debt(
    cash_from_operations: float | None,
    gross_debt: float | None,
) -> float | None:
    return safe_div(cash_from_operations, gross_debt)


def interest_coverage(ebit: float | None, interest_expense: float | None) -> float | None:
    if interest_expense is None:
        return None
    return safe_div(ebit, abs(interest_expense))


def current_ratio(
    current_assets: float | None,
    current_liabilities: float | None,
) -> float | None:
    return safe_div(current_assets, current_liabilities)


def quick_ratio(
    current_assets: float | None,
    inventories: float | None,
    current_liabilities: float | None,
) -> float | None:
    if current_assets is None or inventories is None:
        return None
    return safe_div(current_assets - inventories, current_liabilities)


def cash_ratio(cash: float | None, current_liabilities: float | None) -> float | None:
    return safe_div(cash, current_liabilities)


def net_working_capital(
    current_assets: float | None,
    current_liabilities: float | None,
) -> float | None:
    if current_assets is None or current_liabilities is None:
        return None
    return current_assets - current_liabilities


def working_capital_to_revenue(
    current_assets: float | None,
    current_liabilities: float | None,
    revenue: float | None,
) -> float | None:
    return safe_div(net_working_capital(current_assets, current_liabilities), revenue)


def free_cash_flow(
    cash_from_operations: float | None,
    capex: float | None,
) -> float | None:
    if cash_from_operations is None or capex is None:
        return None
    return cash_from_operations - abs(capex)


def cash_conversion(
    cash_from_operations: float | None,
    net_income: float | None,
) -> float | None:
    return safe_div(cash_from_operations, net_income)


def fcf_yield(fcf: float | None, market_cap: float | None) -> float | None:
    return safe_div(fcf, market_cap)


def capex_to_revenue(capex: float | None, revenue: float | None) -> float | None:
    if capex is None:
        return None
    return safe_div(abs(capex), revenue)


def payout_ratio(
    dividends_and_jcp: float | None,
    net_income: float | None,
) -> float | None:
    return safe_div(dividends_and_jcp, net_income)


def fcf_payout(dividends_and_jcp: float | None, fcf: float | None) -> float | None:
    return safe_div(dividends_and_jcp, fcf)


def dividend_coverage(fcf: float | None, dividends_and_jcp: float | None) -> float | None:
    return safe_div(fcf, dividends_and_jcp)


def asset_turnover(
    revenue: float | None,
    assets_begin: float | None,
    assets_end: float | None,
) -> float | None:
    return safe_div(revenue, average(assets_begin, assets_end))


def inventory_turnover(
    cost_of_goods: float | None,
    inventory_begin: float | None,
    inventory_end: float | None,
) -> float | None:
    if cost_of_goods is None:
        return None
    return safe_div(abs(cost_of_goods), average(inventory_begin, inventory_end))


def receivables_turnover(
    revenue: float | None,
    receivables_begin: float | None,
    receivables_end: float | None,
) -> float | None:
    return safe_div(revenue, average(receivables_begin, receivables_end))


def days_sales_outstanding(
    revenue: float | None,
    receivables_begin: float | None,
    receivables_end: float | None,
    *,
    days: float = 365.0,
) -> float | None:
    turnover = receivables_turnover(revenue, receivables_begin, receivables_end)
    return safe_div(days, turnover)


def days_inventory_outstanding(
    cost_of_goods: float | None,
    inventory_begin: float | None,
    inventory_end: float | None,
    *,
    days: float = 365.0,
) -> float | None:
    turnover = inventory_turnover(cost_of_goods, inventory_begin, inventory_end)
    return safe_div(days, turnover)


def days_payables_outstanding(
    cost_of_goods: float | None,
    payables_begin: float | None,
    payables_end: float | None,
    *,
    days: float = 365.0,
) -> float | None:
    if cost_of_goods is None:
        return None
    turnover = safe_div(abs(cost_of_goods), average(payables_begin, payables_end))
    return safe_div(days, turnover)


def cash_conversion_cycle(
    dso: float | None,
    dio: float | None,
    dpo: float | None,
) -> float | None:
    if dso is None or dio is None or dpo is None:
        return None
    return dso + dio - dpo


def coefficient_of_variation(values: Sequence[float]) -> float | None:
    vals = [float(value) for value in values if math.isfinite(float(value))]
    if len(vals) < 2:
        return None
    mean = sum(vals) / len(vals)
    if mean == 0:
        return None
    variance = sum((value - mean) ** 2 for value in vals) / (len(vals) - 1)
    return math.sqrt(variance) / abs(mean)
