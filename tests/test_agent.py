from datetime import date

from fastapi.testclient import TestClient

from ultimate_stock_analyzer.agent.models import AgentIntent
from ultimate_stock_analyzer.agent.planner import plan_query
from ultimate_stock_analyzer.agent.synthesizer import DeterministicAgentSynthesizer
from ultimate_stock_analyzer.api.main import create_app
from ultimate_stock_analyzer.api.repository import InMemoryAnalysisRepository
from ultimate_stock_analyzer.api.schemas import EvidenceReference, ScoreSet, StockAnalysis
from ultimate_stock_analyzer.scoring.integrated import DecisionStatus


def _stock(ticker: str, investment: float) -> StockAnalysis:
    return StockAnalysis(
        ticker=ticker,
        company_name=f"Company {ticker}",
        sector="Utilities",
        as_of=date(2026, 8, 28),
        current_price=20.0,
        scores=ScoreSet(
            company_quality=82.0,
            investment_attractiveness=investment,
            entry_timing=58.0,
            ranking_score=investment,
            actionability_score=investment * 0.85 + 58.0 * 0.15,
            data_confidence=91.0,
            component_confidence=0.9,
            status=DecisionStatus.ATTRACTIVE,
            rankable=True,
            model_version="1.4.0",
        ),
        evidence=[EvidenceReference(source="CVM", source_document="DFP")],
    )


def test_planner_detects_comparison_without_llm() -> None:
    plan = plan_query("Compare AAAA3 com BBBB4")
    assert plan.intent == AgentIntent.COMPARE
    assert plan.tickers == ("AAAA3", "BBBB4")


def test_agent_endpoint_uses_verified_repository_context() -> None:
    repository = InMemoryAnalysisRepository(analyses=[_stock("AAAA3", 84.0), _stock("BBBB4", 75.0)])
    client = TestClient(create_app(repository, DeterministicAgentSynthesizer()))
    response = client.post("/v1/agent/query", json={"question": "Compare AAAA3 e BBBB4"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["intent"] == "COMPARE"
    assert payload["used_llm"] is False
    assert "84.0" in payload["answer"]
    assert payload["citations"][0]["source"] == "CVM"


def test_agent_does_not_invent_missing_ticker() -> None:
    client = TestClient(create_app(InMemoryAnalysisRepository(), DeterministicAgentSynthesizer()))
    response = client.post("/v1/agent/query", json={"question": "Analise AAAA3"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["confidence"] == 0.0
    assert "não há análise" in payload["answer"].casefold()
