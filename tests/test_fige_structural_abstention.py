from datetime import UTC, datetime
from pathlib import Path

from ultimate_stock_analyzer.domain.master import SectorClassificationRecord
from ultimate_stock_analyzer.scoring.applicability_review import (
    load_structural_applicability_reviews,
)
from ultimate_stock_analyzer.scoring.fige_structural_abstention import (
    ABSTAIN_MODEL_ID,
    evaluate_fige_structural_abstention,
)
from ultimate_stock_analyzer.scoring.sector_models import SectorModelRegistry

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "config/scoring/sector_registry_v0.6.yml"
REVIEWS = ROOT / "config/universe/b3_structural_applicability_reviews_v0.3.json"


def _record(
    company_id: str,
    cvm_code: int,
    issuer_code: str,
    *,
    sector: str,
    subsector: str,
    segment: str,
) -> SectorClassificationRecord:
    return SectorClassificationRecord(
        company_id=company_id,
        cvm_code=cvm_code,
        issuer_code=issuer_code,
        trading_name=issuer_code,
        sector=sector,
        subsector=subsector,
        segment=segment,
        collected_at=datetime(2026, 9, 1, tzinfo=UTC),
    )


def test_registry_routes_fige_segment_to_explicit_abstention() -> None:
    registry = SectorModelRegistry.from_yaml(REGISTRY)

    fige = registry.select(
        {
            "sector": "Financeiro",
            "subsector": "Intermediários Financeiros",
            "segment": "Outros Intermediarios Financeiros",
        }
    )
    bank = registry.select(
        {
            "sector": "Financeiro",
            "subsector": "Intermediários Financeiros",
            "segment": "Bancos",
        }
    )

    assert fige.model_id == ABSTAIN_MODEL_ID
    assert fige.is_fallback is False
    assert bank.model_id == "banks"


def test_abstention_regression_changes_only_fige_and_never_ranks_it() -> None:
    registry = SectorModelRegistry.from_yaml(REGISTRY)
    reviews = load_structural_applicability_reviews(REVIEWS)
    records = [
        _record(
            "cvm:6041",
            6041,
            "FIGE",
            sector="Financeiro",
            subsector="Intermediários Financeiros",
            segment="Outros Intermediarios Financeiros",
        ),
        _record(
            "cvm:1023",
            1023,
            "BBAS",
            sector="Financeiro",
            subsector="Intermediários Financeiros",
            segment="Bancos",
        ),
        _record(
            "cvm:7617",
            7617,
            "ITSA",
            sector="Financeiro",
            subsector="Intermediários Financeiros",
            segment="Holdings Diversificadas",
        ),
        _record(
            "cvm:9999",
            9999,
            "RETL",
            sector="Consumo Cíclico",
            subsector="Comércio",
            segment="Varejo",
        ),
    ]

    report = evaluate_fige_structural_abstention(
        records,
        registry=registry,
        applicability_reviews=reviews,
    )

    assert report.regression_passed is True
    assert report.failures == ()
    assert [item.company_id for item in report.routing_deltas] == ["cvm:6041"]
    assert report.routing_deltas[0].before_model_id == "general_corporate"
    assert report.routing_deltas[0].after_model_id == ABSTAIN_MODEL_ID
    assert report.abstention_company_ids == ("cvm:6041",)
    assert report.fige_review_present is False
    assert report.fige_structural_score == 50.0
    assert report.fige_data_coverage == 0.0
    assert report.fige_confidence == 0.0
    assert report.fige_rankable is False
    assert report.fige_categories == ()
    assert "NO_STRUCTURAL_DATA" in report.fige_flags
    assert report.corporate_metric_probe_invariant is True
    assert report.historical_backtest_executed is False
