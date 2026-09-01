from __future__ import annotations

from pathlib import Path
from typing import Any

from ultimate_stock_analyzer.domain.models import AnalysisResult, RedFlag
from ultimate_stock_analyzer.scoring.engine import ScoringConfig, ScoringEngine
from ultimate_stock_analyzer.universe.current_equity_securities import (
    CurrentBrazilianEquitySecurityUniverseReport,
)
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
        security_universe_report: CurrentBrazilianEquitySecurityUniverseReport,
        red_flags: dict[str, list[RedFlag]] | None = None,
    ) -> tuple[list[AnalysisResult], CurrentAnalysisUniverseGateReport]:
        """Rank only exact current B3 core-equity securities of Brazilian issuers.

        The explicit current-state path requires both issuer-jurisdiction eligibility
        and security-level B3 eligibility before any row reaches the scoring engine.
        It does not replace ``rank`` because these current CVM/B3 controls are not
        point-in-time eligible for historical use.
        """

        eligible_rows, gate_report = partition_current_analysis_rows(
            rows,
            eligibility_report=eligibility_report,
            security_universe_report=security_universe_report,
        )
        return (
            self.engine.score_universe(eligible_rows, red_flags=red_flags),
            gate_report,
        )
