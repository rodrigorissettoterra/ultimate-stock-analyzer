from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class Direction(StrEnum):
    HIGHER = "higher"
    LOWER = "lower"
    TARGET = "target"


class Recommendation(StrEnum):
    VERY_ATTRACTIVE = "VERY_ATTRACTIVE"
    ATTRACTIVE = "ATTRACTIVE"
    WATCH = "WATCH"
    WAIT = "WAIT"
    AVOID = "AVOID"
    BLOCKED = "BLOCKED"


class MetricObservation(BaseModel):
    ticker: str
    metric: str
    value: float | None
    unit: str | None = None
    reference_date: date
    publication_date: date | None = None
    available_from: datetime | None = None
    collected_at: datetime
    source: str
    source_document: str | None = None
    revision: int = 0


class CompanyRecord(BaseModel):
    ticker: str
    company_name: str
    sector: str
    subsector: str | None = None
    segment: str | None = None


class NewsSignal(BaseModel):
    ticker: str
    relevant: bool
    event_type: str
    impact: float = Field(ge=-1.0, le=1.0)
    severity: int = Field(ge=1, le=5)
    confidence: float = Field(ge=0.0, le=1.0)
    rationale: str
    source_url: str | None = None
    published_at: datetime | None = None


class RedFlag(BaseModel):
    code: str
    reason: str
    blocking: bool = False
    severity: int = Field(default=3, ge=1, le=5)


class CategoryScore(BaseModel):
    name: str
    score: float = Field(ge=0.0, le=100.0)
    coverage: float = Field(ge=0.0, le=1.0)
    contributions: dict[str, float] = Field(default_factory=dict)


class AnalysisResult(BaseModel):
    ticker: str
    company_name: str | None = None
    sector: str
    current_price: float | None = None
    dy_ttm: float | None = None
    lending_rate_annual: float | None = None
    lending_utilization: float | None = None
    categories: dict[str, CategoryScore]
    company_quality_score: float
    investment_score: float
    entry_score: float
    final_score: float
    data_confidence: float
    recommendation: Recommendation
    red_flags: list[RedFlag] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
