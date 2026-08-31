from __future__ import annotations

from pathlib import Path
from typing import Any

from ultimate_stock_analyzer.domain.models import AnalysisResult, RedFlag
from ultimate_stock_analyzer.scoring.engine import ScoringConfig, ScoringEngine
from ultimate_stock_analyzer.universe.eligibility import (
    BrazilianEquityEligibilityReport,
)
from ultimate_stock_analyzer.universe.scoring_gate import (
    CurrentAnalysisUniverseGateReport,
    partition_current_analysis_rows,
)


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

    def rank_current_brazilian_equities(
        self,
        rows: list[dict[str, Any]],
        *,
        eligibility_report: BrazilianEquityEligibilityReport,
        red_flags: dict[str, list[RedFlag]] | None = None,
    ) -> tuple[list[AnalysisResult], CurrentAnalysisUniverseGateReport]:
        """Rank a current-state Brazilian-company universe after fail-closed gating.

        This explicit method does not replace ``rank`` because the current CVM
        jurisdiction registries are not point-in-time eligible for historical use.
        """

        eligible_rows, gate_report = partition_current_analysis_rows(
            rows,
            eligibility_report=eligibility_report,
        )
        return (
            self.engine.score_universe(eligible_rows, red_flags=red_flags),
            gate_report,
        )
