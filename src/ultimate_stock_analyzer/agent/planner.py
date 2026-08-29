from __future__ import annotations

import re
import unicodedata

from ultimate_stock_analyzer.agent.models import AgentIntent, AgentPlan

_TICKER_PATTERN = re.compile(r"(?<![A-Z0-9])([A-Z]{4}\d{1,2})(?![A-Z0-9])")


def _plain(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    return "".join(char for char in normalized if not unicodedata.combining(char)).casefold()


def plan_query(question: str) -> AgentPlan:
    normalized_question = question.strip().upper()
    tickers = tuple(dict.fromkeys(_TICKER_PATTERN.findall(normalized_question)))
    plain = _plain(question)

    if len(tickers) >= 2:
        return AgentPlan(AgentIntent.COMPARE, tickers[:5])
    if tickers:
        return AgentPlan(AgentIntent.STOCK_ANALYSIS, tickers)
    if any(term in plain for term in ("backtest", "historico", "desempenho", "performance")):
        return AgentPlan(AgentIntent.BACKTEST, ())
    if any(
        term in plain
        for term in (
            "ranking",
            "melhor",
            "melhores",
            "top ",
            "atrativa",
            "atrativas",
            "oportunidade",
            "oportunidades",
        )
    ):
        return AgentPlan(AgentIntent.RANKING, ())
    return AgentPlan(AgentIntent.UNKNOWN, ())
