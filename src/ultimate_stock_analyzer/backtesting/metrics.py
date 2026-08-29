from __future__ import annotations

from dataclasses import dataclass
from math import sqrt
from statistics import covariance, fmean, median, pstdev, pvariance

from ultimate_stock_analyzer.backtesting.models import BacktestResult


@dataclass(frozen=True, slots=True)
class PerformanceMetrics:
    total_return: float
    benchmark_total_return: float
    cagr: float
    benchmark_cagr: float
    annualized_alpha: float | None
    beta: float | None
    annualized_volatility: float
    sharpe: float | None
    sortino: float | None
    max_drawdown: float
    calmar: float | None
    information_ratio: float | None
    positive_hit_rate: float
    benchmark_hit_rate: float
    average_turnover: float


def _compound(returns: list[float]) -> float:
    value = 1.0
    for period_return in returns:
        value *= 1.0 + period_return
    return value - 1.0


def _max_drawdown(returns: list[float]) -> float:
    equity = 1.0
    peak = 1.0
    worst = 0.0
    for period_return in returns:
        equity *= 1.0 + period_return
        peak = max(peak, equity)
        worst = min(worst, equity / peak - 1.0)
    return worst


def analyze_performance(
    result: BacktestResult,
    *,
    risk_free_rate_annual: float = 0.0,
) -> PerformanceMetrics:
    if not result.periods:
        raise ValueError("backtest contains no periods")
    if risk_free_rate_annual <= -1.0:
        raise ValueError("risk_free_rate_annual must be greater than -1")

    returns = [period.portfolio_return for period in result.periods]
    benchmark = [period.benchmark_return for period in result.periods]
    day_lengths = [
        (period.exit_decision_date - period.decision_date).days
        for period in result.periods
        if period.exit_decision_date > period.decision_date
    ]
    typical_days = median(day_lengths) if day_lengths else 30.4375
    periods_per_year = 365.25 / typical_days
    elapsed_days = (result.periods[-1].exit_decision_date - result.periods[0].decision_date).days
    years = max(elapsed_days / 365.25, 1.0 / periods_per_year)

    total_return = _compound(returns)
    benchmark_total = _compound(benchmark)
    cagr = (1.0 + total_return) ** (1.0 / years) - 1.0 if total_return > -1.0 else -1.0
    benchmark_cagr = (
        (1.0 + benchmark_total) ** (1.0 / years) - 1.0 if benchmark_total > -1.0 else -1.0
    )
    volatility = pstdev(returns) * sqrt(periods_per_year) if len(returns) > 1 else 0.0
    rf_period = (1.0 + risk_free_rate_annual) ** (1.0 / periods_per_year) - 1.0
    excess = [value - rf_period for value in returns]
    benchmark_excess = [value - rf_period for value in benchmark]
    excess_std = pstdev(excess) if len(excess) > 1 else 0.0
    sharpe = fmean(excess) / excess_std * sqrt(periods_per_year) if excess_std > 0 else None
    downside = [min(0.0, value) for value in excess]
    downside_dev = sqrt(fmean([value * value for value in downside])) if downside else 0.0
    sortino = (
        fmean(excess) / downside_dev * sqrt(periods_per_year) if downside_dev > 0 else None
    )
    max_drawdown = _max_drawdown(returns)
    calmar = cagr / abs(max_drawdown) if max_drawdown < 0 else None
    active = [value - bench for value, bench in zip(returns, benchmark, strict=True)]
    active_std = pstdev(active) if len(active) > 1 else 0.0
    information_ratio = (
        fmean(active) / active_std * sqrt(periods_per_year) if active_std > 0 else None
    )

    benchmark_variance = pvariance(benchmark_excess) if len(benchmark_excess) > 1 else 0.0
    beta = (
        covariance(excess, benchmark_excess) / benchmark_variance
        if benchmark_variance > 0 and len(excess) > 1
        else None
    )
    annualized_alpha = (
        (fmean(excess) - beta * fmean(benchmark_excess)) * periods_per_year
        if beta is not None
        else None
    )
    positive_hit_rate = sum(value > 0 for value in returns) / len(returns)
    benchmark_hit_rate = sum(
        value > bench for value, bench in zip(returns, benchmark, strict=True)
    ) / len(returns)
    average_turnover = fmean(period.turnover for period in result.periods)
    return PerformanceMetrics(
        total_return=total_return,
        benchmark_total_return=benchmark_total,
        cagr=cagr,
        benchmark_cagr=benchmark_cagr,
        annualized_alpha=annualized_alpha,
        beta=beta,
        annualized_volatility=volatility,
        sharpe=sharpe,
        sortino=sortino,
        max_drawdown=max_drawdown,
        calmar=calmar,
        information_ratio=information_ratio,
        positive_hit_rate=positive_hit_rate,
        benchmark_hit_rate=benchmark_hit_rate,
        average_turnover=average_turnover,
    )
