from __future__ import annotations

from ultimate_stock_analyzer.agent.context import build_context
from ultimate_stock_analyzer.agent.models import AgentAnswer, AgentCitation
from ultimate_stock_analyzer.agent.planner import plan_query
from ultimate_stock_analyzer.agent.synthesizer import AgentSynthesizer
from ultimate_stock_analyzer.api.service import AnalysisQueryService


class ConversationalAgentService:
    def __init__(
        self,
        query_service: AnalysisQueryService,
        synthesizer: AgentSynthesizer,
    ) -> None:
        self.query_service = query_service
        self.synthesizer = synthesizer

    def answer(self, question: str) -> AgentAnswer:
        plan = plan_query(question)
        context = build_context(plan, self.query_service)
        answer = self.synthesizer.synthesize(question, context)
        citations = self._citations(context.payload)
        return AgentAnswer(
            intent=context.intent,
            answer=answer,
            tickers=list(context.tickers),
            data_as_of=context.data_as_of,
            model_versions=list(context.model_versions),
            confidence=context.confidence,
            citations=citations,
            used_llm=self.synthesizer.uses_llm,
        )

    @staticmethod
    def _citations(payload: dict[str, object]) -> list[AgentCitation]:
        citations: list[AgentCitation] = []
        seen: set[tuple[str, str | None, str | None]] = set()
        stocks = payload.get("stocks", [])
        if not isinstance(stocks, list):
            return citations
        for stock in stocks:
            if not isinstance(stock, dict):
                continue
            evidence = stock.get("evidence", [])
            if not isinstance(evidence, list):
                continue
            for row in evidence:
                if not isinstance(row, dict):
                    continue
                source = row.get("source")
                if not isinstance(source, str):
                    continue
                source_document = row.get("source_document")
                url = row.get("url")
                key = (
                    source,
                    source_document if isinstance(source_document, str) else None,
                    url if isinstance(url, str) else None,
                )
                if key in seen:
                    continue
                seen.add(key)
                citations.append(
                    AgentCitation(source=key[0], source_document=key[1], url=key[2])
                )
        return citations[:20]
