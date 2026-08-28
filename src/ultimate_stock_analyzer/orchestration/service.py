from __future__ import annotations

from pathlib import Path
from typing import Any

from ultimate_stock_analyzer.domain.models import AnalysisResult, RedFlag
from ultimate_stock_analyzer.scoring.engine import ScoringConfig, ScoringEngine


class AnalyzerService:
    def __init__(self, config_path: str | Path) -> None:
        self.config = ScoringConfig.from_yaml(config_path)
        self.engine = ScoringEngine(self.config)

    def rank(
        self,
        rows: list[dict[str, Any]],
        red_flags: dict[str, list[RedFlag]] | None = None,
    ) -> list[AnalysisResult]:
        return self.engine.score_universe(rows, red_flags=red_flags)
