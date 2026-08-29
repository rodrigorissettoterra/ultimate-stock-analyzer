from __future__ import annotations

from collections.abc import Iterable
from typing import Protocol

from ultimate_stock_analyzer.api.schemas import BacktestSummary, StockAnalysis


class AnalysisRepository(Protocol):
    def is_ready(self) -> bool: ...

    def list_stock_analyses(self) -> list[StockAnalysis]: ...

    def get_stock_analysis(self, ticker: str) -> StockAnalysis | None: ...

    def list_backtests(self) -> list[BacktestSummary]: ...

    def get_backtest(self, backtest_id: str) -> BacktestSummary | None: ...


class InMemoryAnalysisRepository:
    """Reference repository for tests, notebooks and local/Colab use."""

    def __init__(
        self,
        analyses: Iterable[StockAnalysis] = (),
        backtests: Iterable[BacktestSummary] = (),
    ) -> None:
        self._analyses = {analysis.ticker.upper(): analysis for analysis in analyses}
        self._backtests = {backtest.backtest_id: backtest for backtest in backtests}

    def is_ready(self) -> bool:
        return True

    def list_stock_analyses(self) -> list[StockAnalysis]:
        return list(self._analyses.values())

    def get_stock_analysis(self, ticker: str) -> StockAnalysis | None:
        return self._analyses.get(ticker.upper())

    def list_backtests(self) -> list[BacktestSummary]:
        return list(self._backtests.values())

    def get_backtest(self, backtest_id: str) -> BacktestSummary | None:
        return self._backtests.get(backtest_id)
