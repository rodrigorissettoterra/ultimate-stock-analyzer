from datetime import UTC, datetime
from pathlib import Path

from ultimate_stock_analyzer.domain.master import SectorClassificationRecord
from ultimate_stock_analyzer.scoring.sector_coverage import profile_sector_model_coverage
from ultimate_stock_analyzer.scoring.sector_models import SectorModelRegistry


def _record(company_id: str, cvm_code: int, issuer_code: str) -> SectorClassificationRecord:
    return SectorClassificationRecord(
        company_id=company_id,
        cvm_code=cvm_code,
        issuer_code=issuer_code,
        trading_name=issuer_code,
        sector="Financeiro",
        subsector="Holdings Diversificadas",
        segment="Holdings Diversificadas",
        collected_at=datetime(2026, 9, 1, tzinfo=UTC),
    )


def test_sector_coverage_propagates_canonical_company_id_to_registry() -> None:
    registry = SectorModelRegistry.from_yaml(
        Path("config/scoring/sector_registry_v0.6.yml")
    )
    records = [
        _record("cvm:7617", 7617, "ITSA"),
        _record("cvm:25887", 25887, "ARND"),
    ]

    report = profile_sector_model_coverage(
        records,
        registry=registry,
        classification_rows=2,
    )

    assert report.model_counts == {
        "general_corporate": 1,
        "itsa_holding_abstain": 1,
    }
    assert report.specialized_companies == 1
    assert report.fallback_companies == 1
    assert report.ambiguous_specialized_matches == 0
