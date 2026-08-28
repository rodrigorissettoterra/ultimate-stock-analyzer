from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel, Field

from ultimate_stock_analyzer.domain.models import AnalysisResult, RedFlag
from ultimate_stock_analyzer.orchestration.service import AnalyzerService

ROOT = Path(__file__).resolve().parents[3]
CONFIG = ROOT / "config" / "scoring" / "model_v0.1.yml"
SERVICE = AnalyzerService(CONFIG)

app = FastAPI(
    title="Ultimate Stock Analyzer API",
    version="0.1.0",
    description="Auditable Brazilian equity research engine. Research only; not individualized advice.",
)


class RankRequest(BaseModel):
    rows: list[dict[str, Any]] = Field(min_length=1)
    red_flags: dict[str, list[RedFlag]] = Field(default_factory=dict)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "model_version": SERVICE.config.version}


@app.post("/ranking", response_model=list[AnalysisResult])
def ranking(request: RankRequest) -> list[AnalysisResult]:
    return SERVICE.rank(request.rows, red_flags=request.red_flags)
