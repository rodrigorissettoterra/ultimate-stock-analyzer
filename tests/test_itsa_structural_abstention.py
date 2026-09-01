from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from ultimate_stock_analyzer.domain.master import SectorClassificationRecord
from ultimate_stock_analyzer.scoring.applicability_review import (
    load_structural_applicability_reviews,
)
from ultimate_stock_analyzer.scoring.itsa_structural_abstention import (
    ITSA_COMPANY_ID,
    evaluate_itsa_structural_abstention,
)
from ultimate_stock_analyzer.scoring.sector_models import SectorModelRegistry

REGISTRY = Path("config/scoring/sector_registry_v0.6.yml")
REVIEWS = Path("config/universe/b3_structural_applicability_reviews_v0.4.json")


def _record(
    company_id: str,
    cvm_code: int,
    issuer_code: str,
    *,
    segment: str = "Holdings Diversificadas",
) -> SectorClassificationRecord:
    return SectorClassificationRecord(
        company_id=company_id,
        cvm_code=cvm_code,
        issuer_code=issuer_code,
        trading_name=issuer_code,
        sector="Financeiro",
        subsector="Holdings Diversificadas",
        segment=segment,
        collected_at=datetime(2026, 9, 1, tzinfo=UTC),
    )


def test_itsa_abstention_changes_only_itsa_and_preserves_segment_neighbors() -> None:
    registry = SectorModelRegistry.from_yaml(REGISTRY)
    reviews = load_structural_applicability_reviews(REVIEWS)
    records = [
        _record(ITSA_COMPANY_ID, 7617, "ITSA"),
        _record("cvm:25887", 25887, "ARND"),
        _record("cvm:15458", 15458, "EPAR"),
        _record("cvm:25003", 25003, "SIMH"),
    ]

    report = evaluate_itsa_structural_abstention(
        records,
        registry=registry,
        applicability_reviews=reviews,
    )

    assert report.regression_passed is True
    assert report.failures == ()
    assert [delta.company_id for delta in report.routing_deltas] == [ITSA_COMPANY_ID]
    assert report.abstention_company_ids == (ITSA_COMPANY_ID,)
    assert {
        route.company_id: route.model_id for route in report.exact_segment_neighbor_routes
    } == {
        "cvm:15458": "general_corporate",
        "cvm:25003": "general_corporate",
        "cvm:25887": "general_corporate",
    }
    assert all(route.is_fallback for route in report.exact_segment_neighbor_routes)
    assert report.itsa_selection_reason == "company_id:cvm:7617"
    assert report.itsa_model_id == "itsa_holding_abstain"
    assert report.itsa_model_family == "itsa_holding_abstain_v1"
    assert report.itsa_structural_score == 50.0
    assert report.itsa_data_coverage == 0.0
    assert report.itsa_confidence == 0.0
    assert report.itsa_rankable is False
    assert report.itsa_categories == ()
    assert report.corporate_metric_probe_invariant is True
    assert report.itsa_review_present is False
    assert report.historical_backtest_executed is False
