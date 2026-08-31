from pathlib import Path
from typing import Any

import pytest

from ultimate_stock_analyzer.orchestration.service import AnalyzerService
from ultimate_stock_analyzer.universe.eligibility import (
    classify_brazilian_equity_issuers,
)
from ultimate_stock_analyzer.universe.scoring_gate import (
    partition_current_analysis_rows,
)


def _eligibility():
    return classify_brazilian_equity_issuers(
        ("cvm:1", "cvm:2", "cvm:3", "cvm:4"),
        brazilian_public_company_ids=("cvm:1", "cvm:2", "cvm:4"),
        foreign_issuer_company_ids=("cvm:3", "cvm:4"),
    )


def test_current_analysis_gate_keeps_only_eligible_rows_and_preserves_diagnostics() -> None:
    eligibility = _eligibility()
    rows = [
        {"company_id": "cvm:1", "ticker": "ONE3"},
        {"company_id": "cvm:3", "ticker": "FORE11"},
        {"company_id": "cvm:4", "ticker": "CONFLICT3"},
    ]

    eligible, report = partition_current_analysis_rows(
        rows,
        eligibility_report=eligibility,
    )

    assert [row["ticker"] for row in eligible] == ["ONE3"]
    assert report.analysis_rows == 3
    assert report.eligible_rows == 1
    assert report.excluded_rows == 2
    assert report.point_in_time_eligible is False
    assert report.scope == "CURRENT_STATE_ONLY"
    assert [item.company_id for item in report.exclusions] == ["cvm:3", "cvm:4"]
    assert report.exclusions[0].status == "EXCLUDED_FOREIGN_ISSUER"
    assert report.exclusions[1].status == "CONFLICTING_CVM_REGISTRY_CLASSIFICATION"


def test_current_analysis_gate_excludes_unresolved_identity() -> None:
    eligibility = classify_brazilian_equity_issuers(
        ("cvm:999",),
        brazilian_public_company_ids=(),
        foreign_issuer_company_ids=(),
    )

    eligible, report = partition_current_analysis_rows(
        ({"company_id": "cvm:999", "ticker": "MISS3"},),
        eligibility_report=eligibility,
    )

    assert eligible == []
    assert report.excluded_rows == 1
    assert report.exclusions[0].status == "UNRESOLVED_CVM_REGISTRY_CLASSIFICATION"


def test_current_analysis_gate_fails_closed_without_canonical_identity() -> None:
    with pytest.raises(ValueError, match="requires canonical company_id"):
        partition_current_analysis_rows(
            ({"ticker": "NOID3"},),
            eligibility_report=_eligibility(),
        )


def test_current_analysis_gate_fails_closed_without_eligibility_decision() -> None:
    with pytest.raises(ValueError, match="lacks a universe eligibility decision"):
        partition_current_analysis_rows(
            ({"company_id": "cvm:999", "ticker": "MISS3"},),
            eligibility_report=_eligibility(),
        )


def test_analyzer_service_filters_before_invoking_scoring_engine() -> None:
    root = Path(__file__).resolve().parents[1]
    service = AnalyzerService(root / "config/scoring/model_v0.1.yml")

    class CapturingEngine:
        def __init__(self) -> None:
            self.rows: list[dict[str, Any]] = []

        def score_universe(
            self,
            rows: list[dict[str, Any]],
            red_flags: object = None,
        ) -> list[Any]:
            self.rows = rows
            return []

    engine = CapturingEngine()
    service.engine = engine  # type: ignore[assignment]
    rows = [
        {"company_id": "cvm:1", "ticker": "ONE3"},
        {"company_id": "cvm:2", "ticker": "TWO3"},
        {"company_id": "cvm:3", "ticker": "FORE11"},
    ]

    results, report = service.rank_current_brazilian_equities(
        rows,
        eligibility_report=_eligibility(),
    )

    assert results == []
    assert [row["company_id"] for row in engine.rows] == ["cvm:1", "cvm:2"]
    assert report.excluded_rows == 1
    assert report.exclusions[0].company_id == "cvm:3"
