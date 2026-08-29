from __future__ import annotations

from ultimate_stock_analyzer.api.repository import AnalysisRepository
from ultimate_stock_analyzer.api.schemas import (
    BacktestSummary,
    RankingItem,
    RankingPage,
    StockAnalysis,
)
from ultimate_stock_analyzer.scoring.integrated import DecisionStatus


class AnalysisQueryService:
    def __init__(self, repository: AnalysisRepository) -> None:
        self.repository = repository

    def ranking(
        self,
        *,
        sector: str | None = None,
        status: DecisionStatus | None = None,
        min_investment_score: float | None = None,
        rankable_only: bool = True,
        limit: int = 50,
        offset: int = 0,
    ) -> RankingPage:
        rows = self.repository.list_stock_analyses()
        if sector is not None:
            normalized_sector = sector.casefold().strip()
            rows = [row for row in rows if row.sector.casefold() == normalized_sector]
        if status is not None:
            rows = [row for row in rows if row.scores.status == status]
        if min_investment_score is not None:
            rows = [
                row
                for row in rows
                if row.scores.investment_attractiveness >= min_investment_score
            ]
        if rankable_only:
            rows = [row for row in rows if row.scores.rankable]

        ordered = sorted(
            rows,
            key=lambda row: (-row.scores.investment_attractiveness, row.ticker),
        )
        total = len(ordered)
        page = ordered[offset : offset + limit]
        items = [
            self._ranking_item(row, rank=offset + index + 1)
            for index, row in enumerate(page)
        ]
        as_of = max((row.as_of for row in ordered), default=None)
        return RankingPage(items=items, total=total, limit=limit, offset=offset, as_of=as_of)

    def stock(self, ticker: str) -> StockAnalysis | None:
        return self.repository.get_stock_analysis(ticker.strip().upper())

    def backtests(self) -> list[BacktestSummary]:
        return sorted(
            self.repository.list_backtests(),
            key=lambda row: (row.end_date, row.backtest_id),
            reverse=True,
        )

    def backtest(self, backtest_id: str) -> BacktestSummary | None:
        return self.repository.get_backtest(backtest_id)

    @staticmethod
    def _ranking_item(row: StockAnalysis, *, rank: int) -> RankingItem:
        return RankingItem(
            rank=rank,
            ticker=row.ticker,
            company_name=row.company_name,
            sector=row.sector,
            current_price=row.current_price,
            dy_ttm=row.dy_ttm,
            lending_rate_annual=row.lending_rate_annual,
            lending_utilization=row.lending_utilization,
            investment_attractiveness=row.scores.investment_attractiveness,
            company_quality=row.scores.company_quality,
            entry_timing=row.scores.entry_timing,
            data_confidence=row.scores.data_confidence,
            status=row.scores.status,
            model_version=row.scores.model_version,
            as_of=row.as_of,
        )
