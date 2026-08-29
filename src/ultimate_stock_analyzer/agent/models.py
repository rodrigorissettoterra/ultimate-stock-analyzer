from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AgentIntent(StrEnum):
    STOCK_ANALYSIS = "STOCK_ANALYSIS"
    COMPARE = "COMPARE"
    RANKING = "RANKING"
    BACKTEST = "BACKTEST"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True, slots=True)
class AgentPlan:
    intent: AgentIntent
    tickers: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class AgentContext:
    intent: AgentIntent
    tickers: tuple[str, ...]
    payload: dict[str, Any]
    data_as_of: date | None
    model_versions: tuple[str, ...]
    confidence: float


class AgentCitation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: str
    source_document: str | None = None
    url: str | None = None


class AgentAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid")

    intent: AgentIntent
    answer: str
    tickers: list[str] = Field(default_factory=list)
    data_as_of: date | None = None
    model_versions: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    citations: list[AgentCitation] = Field(default_factory=list)
    used_llm: bool = False
