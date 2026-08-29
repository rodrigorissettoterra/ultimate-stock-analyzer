from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from ultimate_stock_analyzer.scoring.integrated import DecisionStatus


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EvidenceReference(StrictModel):
    source: str
    source_document: str | None = None
    url: str | None = None
    reference_date: date | None = None
    published_at: datetime | None = None


class ScoreSet(StrictModel):
    company_quality: float = Field(ge=0.0, le=100.0)
    investment_attractiveness: float = Field(ge=0.0, le=100.0)
    entry_timing: float = Field(ge=0.0, le=100.0)
    ranking_score: float = Field(ge=0.0, le=100.0)
    actionability_score: float = Field(ge=0.0, le=100.0)
    data_confidence: float = Field(ge=0.0, le=100.0)
    component_confidence: float = Field(ge=0.0, le=1.0)
    status: DecisionStatus
    rankable: bool
    model_version: str
    components: dict[str, float] = Field(default_factory=dict)
    flags: list[str] = Field(default_factory=list)


class StockAnalysis(StrictModel):
    ticker: str
    company_name: str
    sector: str
    subsector: str | None = None
    segment: str | None = None
    as_of: date
    current_price: float | None = Field(default=None, gt=0.0)
    dy_ttm: float | None = None
    lending_rate_annual: float | None = None
    lending_utilization: float | None = None
    scores: ScoreSet
    evidence: list[EvidenceReference] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class RankingItem(StrictModel):
    rank: int = Field(ge=1)
    ticker: str
    company_name: str
    sector: str
    current_price: float | None = None
    dy_ttm: float | None = None
    lending_rate_annual: float | None = None
    lending_utilization: float | None = None
    investment_attractiveness: float
    company_quality: float
    entry_timing: float
    data_confidence: float
    status: DecisionStatus
    model_version: str
    as_of: date


class RankingPage(StrictModel):
    items: list[RankingItem]
    total: int = Field(ge=0)
    limit: int = Field(ge=1)
    offset: int = Field(ge=0)
    as_of: date | None = None


class BacktestSummary(StrictModel):
    backtest_id: str
    model_version: str
    start_date: date
    end_date: date
    benchmark: str
    total_return: float
    benchmark_total_return: float
    cagr: float
    benchmark_cagr: float
    max_drawdown: float
    sharpe: float | None = None
    sortino: float | None = None
    information_ratio: float | None = None
    average_turnover: float
    metadata: dict[str, Any] = Field(default_factory=dict)


class AgentQueryRequest(StrictModel):
    question: str = Field(min_length=2, max_length=2000)


class HealthResponse(StrictModel):
    status: str
    api_version: str


class ApiMetadata(StrictModel):
    api_version: str
    default_model_family: str
    ranking_semantics: str
    entry_semantics: str
    disclaimer: str
