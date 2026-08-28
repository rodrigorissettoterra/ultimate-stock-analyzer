from __future__ import annotations

import math
from collections.abc import Sequence


def _finite(value: float, name: str) -> float:
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{name} must be finite")
    return result


def _positive(value: float, name: str) -> float:
    result = _finite(value, name)
    if result <= 0:
        raise ValueError(f"{name} must be positive")
    return result


def _validate_discount_rate(rate: float, terminal_growth: float, name: str) -> tuple[float, float]:
    discount = _finite(rate, name)
    growth = _finite(terminal_growth, "terminal_growth")
    if discount <= growth:
        raise ValueError(f"{name} must be greater than terminal_growth")
    if discount <= -1.0:
        raise ValueError(f"{name} must be greater than -1")
    return discount, growth


def discounted_cash_flow_per_share(
    *,
    fcff0: float,
    growth_rates: Sequence[float],
    wacc: float,
    terminal_growth: float,
    net_debt: float,
    diluted_shares: float,
) -> float:
    """Return FCFF DCF equity value per share.

    Forecast assumptions must be supplied explicitly. The function never invents growth,
    discount rates or capital structure assumptions.
    """
    if not growth_rates:
        raise ValueError("growth_rates must contain at least one forecast year")
    discount, terminal = _validate_discount_rate(wacc, terminal_growth, "wacc")
    shares = _positive(diluted_shares, "diluted_shares")
    cash_flow = _finite(fcff0, "fcff0")
    debt = _finite(net_debt, "net_debt")

    enterprise_value = 0.0
    for year, growth in enumerate(growth_rates, start=1):
        cash_flow *= 1.0 + _finite(float(growth), "growth_rate")
        enterprise_value += cash_flow / (1.0 + discount) ** year

    terminal_cash_flow = cash_flow * (1.0 + terminal)
    terminal_value = terminal_cash_flow / (discount - terminal)
    enterprise_value += terminal_value / (1.0 + discount) ** len(growth_rates)
    return (enterprise_value - debt) / shares


def two_stage_ddm_per_share(
    *,
    dividend0: float,
    growth_rates: Sequence[float],
    cost_of_equity: float,
    terminal_growth: float,
) -> float:
    """Return a two-stage dividend-discount value per share."""
    if not growth_rates:
        raise ValueError("growth_rates must contain at least one forecast year")
    discount, terminal = _validate_discount_rate(
        cost_of_equity,
        terminal_growth,
        "cost_of_equity",
    )
    dividend = _finite(dividend0, "dividend0")
    if dividend < 0:
        raise ValueError("dividend0 cannot be negative")

    value = 0.0
    for year, growth in enumerate(growth_rates, start=1):
        dividend *= 1.0 + _finite(float(growth), "growth_rate")
        value += dividend / (1.0 + discount) ** year

    terminal_dividend = dividend * (1.0 + terminal)
    terminal_value = terminal_dividend / (discount - terminal)
    return value + terminal_value / (1.0 + discount) ** len(growth_rates)


def residual_income_per_share(
    *,
    book_value_per_share: float,
    roe_path: Sequence[float],
    cost_of_equity: float,
    payout_ratio: float,
    terminal_roe: float,
    terminal_growth: float,
) -> float:
    """Return residual-income equity value per share.

    This model is useful for financial institutions where enterprise-value leverage metrics
    are not economically comparable with industrial companies.
    """
    if not roe_path:
        raise ValueError("roe_path must contain at least one forecast year")
    discount, terminal = _validate_discount_rate(
        cost_of_equity,
        terminal_growth,
        "cost_of_equity",
    )
    book0 = _positive(book_value_per_share, "book_value_per_share")
    payout = _finite(payout_ratio, "payout_ratio")
    if not 0.0 <= payout <= 1.0:
        raise ValueError("payout_ratio must be between 0 and 1")

    book = book0
    present_value_residual_income = 0.0
    for year, raw_roe in enumerate(roe_path, start=1):
        roe = _finite(float(raw_roe), "roe")
        earnings = book * roe
        residual_income = earnings - discount * book
        present_value_residual_income += residual_income / (1.0 + discount) ** year
        book += earnings * (1.0 - payout)

    continuing_residual_income = book * (_finite(terminal_roe, "terminal_roe") - discount)
    terminal_value = continuing_residual_income * (1.0 + terminal) / (discount - terminal)
    present_value_residual_income += terminal_value / (1.0 + discount) ** len(roe_path)
    return book0 + present_value_residual_income


def equity_multiple_value_per_share(*, metric_per_share: float, target_multiple: float) -> float:
    """Return equity value from a per-share fundamental and an explicit target multiple."""
    metric = _finite(metric_per_share, "metric_per_share")
    multiple = _positive(target_multiple, "target_multiple")
    return metric * multiple


def enterprise_multiple_value_per_share(
    *,
    operating_metric: float,
    target_multiple: float,
    net_debt: float,
    diluted_shares: float,
) -> float:
    """Convert a target enterprise multiple into equity value per share."""
    metric = _finite(operating_metric, "operating_metric")
    multiple = _positive(target_multiple, "target_multiple")
    shares = _positive(diluted_shares, "diluted_shares")
    debt = _finite(net_debt, "net_debt")
    return (metric * multiple - debt) / shares
