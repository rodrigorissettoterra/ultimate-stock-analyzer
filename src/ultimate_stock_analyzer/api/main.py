from __future__ import annotations

import os
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, HTTPException, Query
from fastapi.staticfiles import StaticFiles

from ultimate_stock_analyzer.agent.models import AgentAnswer
from ultimate_stock_analyzer.agent.service import ConversationalAgentService
from ultimate_stock_analyzer.agent.synthesizer import (
    AgentSynthesizer,
    DeterministicAgentSynthesizer,
    OpenAICompatibleAgentSynthesizer,
)
from ultimate_stock_analyzer.api.repository import AnalysisRepository, InMemoryAnalysisRepository
from ultimate_stock_analyzer.api.schemas import (
    AgentQueryRequest,
    ApiMetadata,
    BacktestSummary,
    HealthResponse,
    RankingPage,
    ScoreSet,
    StockAnalysis,
)
from ultimate_stock_analyzer.api.service import AnalysisQueryService
from ultimate_stock_analyzer.scoring.integrated import DecisionStatus

API_VERSION = "1.0.0"
WEB_DIRECTORY = Path(__file__).resolve().parents[1] / "web"


def _environment_synthesizer() -> AgentSynthesizer:
    api_key = os.getenv("USA_LLM_API_KEY", "").strip()
    model = os.getenv("USA_LLM_MODEL", "").strip()
    if not api_key or not model:
        return DeterministicAgentSynthesizer()
    timeout = float(os.getenv("USA_LLM_TIMEOUT_SECONDS", "30"))
    return OpenAICompatibleAgentSynthesizer(
        api_key=api_key,
        model=model,
        base_url=os.getenv("USA_LLM_BASE_URL", "https://api.openai.com/v1"),
        timeout_seconds=timeout,
    )


def create_app(
    repository: AnalysisRepository | None = None,
    agent_synthesizer: AgentSynthesizer | None = None,
) -> FastAPI:
    query_service = AnalysisQueryService(repository or InMemoryAnalysisRepository())
    agent_service = ConversationalAgentService(
        query_service,
        agent_synthesizer or _environment_synthesizer(),
    )
    application = FastAPI(
        title="Ultimate Stock Analyzer API",
        version=API_VERSION,
        description=(
            "Auditable Brazilian equity research API. Scores are deterministic/versioned; "
            "LLM output is evidence input only. Research support, not individualized advice."
        ),
    )

    @application.get("/health", response_model=HealthResponse, tags=["system"])
    def health() -> HealthResponse:
        return HealthResponse(status="ok", api_version=API_VERSION)

    @application.get("/v1/meta", response_model=ApiMetadata, tags=["system"])
    def metadata() -> ApiMetadata:
        return ApiMetadata(
            api_version=API_VERSION,
            default_model_family="integrated-decision",
            ranking_semantics="Investment Attractiveness is the primary ranking score.",
            entry_semantics="Entry Timing is separate and never changes Investment Attractiveness.",
            disclaimer="Research support only; no guarantee of returns or individualized advice.",
        )

    @application.get("/v1/ranking", response_model=RankingPage, tags=["analysis"])
    def ranking(
        sector: Annotated[str | None, Query(min_length=1, max_length=80)] = None,
        status: DecisionStatus | None = None,
        min_investment_score: Annotated[float | None, Query(ge=0.0, le=100.0)] = None,
        rankable_only: bool = True,
        limit: Annotated[int, Query(ge=1, le=200)] = 50,
        offset: Annotated[int, Query(ge=0)] = 0,
    ) -> RankingPage:
        return query_service.ranking(
            sector=sector,
            status=status,
            min_investment_score=min_investment_score,
            rankable_only=rankable_only,
            limit=limit,
            offset=offset,
        )

    @application.get("/v1/stocks/{ticker}", response_model=StockAnalysis, tags=["analysis"])
    def stock(ticker: str) -> StockAnalysis:
        result = query_service.stock(ticker)
        if result is None:
            raise HTTPException(status_code=404, detail="ticker not found")
        return result

    @application.get("/v1/stocks/{ticker}/scores", response_model=ScoreSet, tags=["analysis"])
    def stock_scores(ticker: str) -> ScoreSet:
        result = query_service.stock(ticker)
        if result is None:
            raise HTTPException(status_code=404, detail="ticker not found")
        return result.scores

    @application.get("/v1/backtests", response_model=list[BacktestSummary], tags=["validation"])
    def backtests() -> list[BacktestSummary]:
        return query_service.backtests()

    @application.get(
        "/v1/backtests/{backtest_id}",
        response_model=BacktestSummary,
        tags=["validation"],
    )
    def backtest(backtest_id: str) -> BacktestSummary:
        result = query_service.backtest(backtest_id)
        if result is None:
            raise HTTPException(status_code=404, detail="backtest not found")
        return result

    @application.post("/v1/agent/query", response_model=AgentAnswer, tags=["agent"])
    def agent_query(request: AgentQueryRequest) -> AgentAnswer:
        return agent_service.answer(request.question)

    application.mount(
        "/dashboard",
        StaticFiles(directory=WEB_DIRECTORY, html=True),
        name="dashboard",
    )
    return application


app = create_app()
