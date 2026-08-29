from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Annotated
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import RequestResponseEndpoint
from starlette.responses import Response

from ultimate_stock_analyzer.agent.models import AgentAnswer
from ultimate_stock_analyzer.agent.service import ConversationalAgentService
from ultimate_stock_analyzer.agent.synthesizer import (
    AgentSynthesizer,
    DeterministicAgentSynthesizer,
    OpenAICompatibleAgentSynthesizer,
)
from ultimate_stock_analyzer.api.repository import AnalysisRepository
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
from ultimate_stock_analyzer.runtime.logging import configure_logging
from ultimate_stock_analyzer.runtime.repository_factory import build_repository
from ultimate_stock_analyzer.runtime.settings import RuntimeSettings
from ultimate_stock_analyzer.scoring.integrated import DecisionStatus

API_VERSION = "1.0.0"
WEB_DIRECTORY = Path(__file__).resolve().parents[1] / "web"
logger = logging.getLogger(__name__)


def _settings_synthesizer(settings: RuntimeSettings) -> AgentSynthesizer:
    if not settings.llm_api_key.strip() or not settings.llm_model.strip():
        return DeterministicAgentSynthesizer()
    return OpenAICompatibleAgentSynthesizer(
        api_key=settings.llm_api_key,
        model=settings.llm_model,
        base_url=settings.llm_base_url,
        timeout_seconds=settings.llm_timeout_seconds,
    )


def create_app(
    repository: AnalysisRepository | None = None,
    agent_synthesizer: AgentSynthesizer | None = None,
    settings: RuntimeSettings | None = None,
) -> FastAPI:
    runtime_settings = settings or RuntimeSettings()
    configure_logging(runtime_settings.log_level)
    effective_repository = repository or build_repository(runtime_settings)
    query_service = AnalysisQueryService(effective_repository)
    agent_service = ConversationalAgentService(
        query_service,
        agent_synthesizer or _settings_synthesizer(runtime_settings),
    )
    application = FastAPI(
        title="Ultimate Stock Analyzer API",
        version=API_VERSION,
        description=(
            "Auditable Brazilian equity research API. Scores are deterministic/versioned; "
            "LLM output is evidence input only. Research support, not individualized advice."
        ),
    )

    @application.middleware("http")
    async def request_log_middleware(
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        request_id = str(uuid4())
        started = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            logger.exception(
                "http_request_failed",
                extra={
                    "event": "http_request_failed",
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                },
            )
            raise
        duration_ms = (time.perf_counter() - started) * 1000.0
        response.headers["X-Request-ID"] = request_id
        logger.info(
            "http_request",
            extra={
                "event": "http_request",
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": round(duration_ms, 3),
            },
        )
        return response

    @application.get("/health", response_model=HealthResponse, tags=["system"])
    def health() -> HealthResponse:
        return HealthResponse(status="ok", api_version=API_VERSION)

    @application.get("/ready", response_model=HealthResponse, tags=["system"])
    def ready() -> HealthResponse:
        if not effective_repository.is_ready():
            raise HTTPException(status_code=503, detail="repository unavailable")
        return HealthResponse(status="ready", api_version=API_VERSION)

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
