from datetime import date

from ultimate_stock_analyzer.backtesting.metrics import analyze_performance
from ultimate_stock_analyzer.backtesting.models import BacktestResult, PeriodObservation


def test_performance_metrics_report_drawdown_and_benchmark_comparison() -> None:
    periods = (
        PeriodObservation(date(2024, 1, 1), date(2024, 2, 1), 0.10, 0.05, 1.0, ("AAA3",)),
        PeriodObservation(date(2024, 2, 1), date(2024, 3, 1), -0.05, -0.02, 0.4, ("AAA3",)),
        PeriodObservation(date(2024, 3, 1), date(2024, 4, 1), 0.08, 0.03, 0.2, ("AAA3",)),
    )
    result = BacktestResult(periods=periods, ending_equity=1.0, model_versions=("1.4.0",))
    metrics = analyze_performance(result)
    assert metrics.total_return > metrics.benchmark_total_return
    assert metrics.max_drawdown < 0
    assert metrics.benchmark_hit_rate > 0.5
    assert metrics.average_turnover > 0
