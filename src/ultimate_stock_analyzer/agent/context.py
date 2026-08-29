from __future__ import annotations

from datetime import date
from statistics import fmean
from typing import Any

from ultimate_stock_analyzer.agent.models import AgentContext, AgentIntent, AgentPlan
from ultimate_stock_analyzer.api.schemas import StockAnalysis
from ultimate_stock_analyzer.api.service import AnalysisQueryService


def _stock_payload(row: StockAnalysis) -> dict[str, Any]:
    return row.model_dump(mode="json")


def _versions(rows: list[StockAnalysis]) -> tuple[str, ...]:
    return tuple(sorted({row.scores.model_version for row in rows}))


def _latest_date(rows: list[StockAnalysis]) -> date | None:
    return max((row.as_of for row in rows), default=None)


def build_context(plan: AgentPlan, query_service: AnalysisQueryService) -> AgentContext:
    if plan.intent in {AgentIntent.STOCK_ANALYSIS, AgentIntent.COMPARE}:
        rows = [row for ticker in plan.tickers if (row := query_service.stock(ticker)) is not None]
        missing = [ticker for ticker in plan.tickers if query_service.stock(ticker) is None]
        confidence = fmean(row.scores.data_confidence / 100.0 for row in rows) if rows else 0.0
        return AgentContext(
            intent=plan.intent,
            tickers=plan.tickers,
            payload={"stocks": [_stock_payload(row) for row in rows], "missing_tickers": missing},
            data_as_of=_latest_date(rows),
            model_versions=_versions(rows),
            confidence=confidence,
        )

    if plan.intent == AgentIntent.RANKING:
        page = query_service.ranking(limit=5, rankable_only=True)
        confidence = (
            fmean(item.data_confidence / 100.0 for item in page.items) if page.items else 0.0
        )
        return AgentContext(
            intent=plan.intent,
            tickers=tuple(item.ticker for item in page.items),
            payload={"ranking": [item.model_dump(mode="json") for item in page.items]},
            data_as_of=page.as_of,
            model_versions=tuple(sorted({item.model_version for item in page.items})),
            confidence=confidence,
        )

    if plan.intent == AgentIntent.BACKTEST:
        rows = query_service.backtests()[:5]
        return AgentContext(
            intent=plan.intent,
            tickers=(),
            payload={"backtests": [row.model_dump(mode="json") for row in rows]},
            data_as_of=max((row.end_date for row in rows), default=None),
            model_versions=tuple(sorted({row.model_version for row in rows})),
            confidence=0.85 if rows else 0.0,
        )

    return AgentContext(
        intent=AgentIntent.UNKNOWN,
        tickers=(),
        payload={},
        data_as_of=None,
        model_versions=(),
        confidence=0.20,
    )
