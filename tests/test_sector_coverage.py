from datetime import UTC, datetime

import pytest

from ultimate_stock_analyzer.domain.master import SectorClassificationRecord
from ultimate_stock_analyzer.scoring.sector_coverage import profile_sector_model_coverage
from ultimate_stock_analyzer.scoring.sector_models import (
    SectorModelDefinition,
    SectorModelRegistry,
)


def _record(
    company_id: str,
    issuer_code: str,
    *,
    sector: str,
    subsector: str,
    segment: str,
) -> SectorClassificationRecord:
    return SectorClassificationRecord(
        company_id=company_id,
        cvm_code=company_id.split(":", 1)[1],
        cnpj="33000167000101",
        issuer_code=issuer_code,
        trading_name=company_id,
        sector=sector,
        subsector=subsector,
        segment=segment,
        listing_segment=None,
        collected_at=datetime(2026, 8, 31, tzinfo=UTC),
    )


def _registry() -> SectorModelRegistry:
    default = SectorModelDefinition(model_id="general_corporate", config_path=__file__)
    return SectorModelRegistry(
        version="test",
        default_model=default,
        models=(
            SectorModelDefinition(
                model_id="banks",
                config_path=__file__,
                priority=100,
                segment_contains=("bancos",),
            ),
            SectorModelDefinition(
                model_id="utilities",
                config_path=__file__,
                priority=80,
                sector_contains=("utilidade pública",),
                subsector_contains=("energia elétrica",),
            ),
        ),
    )


def test_sector_coverage_profiles_catalog_join_and_model_assignment() -> None:
    report = profile_sector_model_coverage(
        [
            _record(
                "cvm:1",
                "BANK",
                sector="Financeiro",
                subsector="Intermediários Financeiros",
                segment="Bancos",
            ),
            _record(
                "cvm:2",
                "UTIL",
                sector="Utilidade Pública",
                subsector="Energia Elétrica",
                segment="Energia Elétrica",
            ),
            _record(
                "cvm:3",
                "RETL",
                sector="Consumo",
                subsector="Comércio",
                segment="Varejo",
            ),
        ],
        registry=_registry(),
        classification_rows=4,
        outside_active_company_catalog_issuer_codes=("CRI1",),
    )

    assert report.classification_rows == 4
    assert report.company_catalog_mapped_rows == 3
    assert report.company_catalog_unmapped_rows == 1
    assert report.company_catalog_join_coverage == 0.75
    assert report.outside_active_company_catalog_issuer_codes == ("CRI1",)
    assert report.normalized_companies == 3
    assert report.model_counts == {"banks": 1, "general_corporate": 1, "utilities": 1}
    assert report.specialized_companies == 2
    assert report.fallback_companies == 1
    assert report.specialized_coverage == 2 / 3


def test_sector_coverage_reports_overlapping_specialized_rules() -> None:
    report = profile_sector_model_coverage(
        [
            _record(
                "cvm:2",
                "UTIL",
                sector="Utilidade Pública",
                subsector="Energia Elétrica",
                segment="Energia Elétrica",
            ),
        ],
        registry=_registry(),
        classification_rows=1,
    )
    assert report.ambiguous_specialized_matches == 0


def test_sector_coverage_rejects_impossible_outside_catalog_count() -> None:
    with pytest.raises(ValueError, match="exceeds"):
        profile_sector_model_coverage(
            [],
            registry=_registry(),
            classification_rows=0,
            outside_active_company_catalog_issuer_codes=("CRI1",),
        )
