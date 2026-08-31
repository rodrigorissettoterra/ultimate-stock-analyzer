from datetime import UTC, datetime

import pytest

from ultimate_stock_analyzer.domain.master import SectorClassificationRecord
from ultimate_stock_analyzer.scoring.sector_coverage import (
    SectorCoverageCompanySample,
    profile_sector_model_coverage,
)
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
        verified_non_equity_issuer_codes=("CRI1",),
    )

    assert report.classification_rows == 4
    assert report.company_catalog_mapped_rows == 3
    assert report.company_catalog_unmapped_rows == 1
    assert report.company_catalog_join_coverage == 0.75
    assert report.verified_non_equity_exclusions == 1
    assert report.unresolved_outside_catalog_rows == 0
    assert report.equity_candidate_identity_coverage == 1.0
    assert report.outside_active_company_catalog_issuer_codes == ("CRI1",)
    assert report.verified_non_equity_issuer_codes == ("CRI1",)
    assert report.unresolved_outside_catalog_issuer_codes == ()
    assert report.normalized_companies == 3
    assert report.model_counts == {"banks": 1, "general_corporate": 1, "utilities": 1}
    assert report.specialized_companies == 2
    assert report.fallback_companies == 1
    assert report.specialized_coverage == 2 / 3
    assert report.fallback_by_sector == {"Consumo": 1}
    assert report.fallback_by_subsector == {"Consumo / Comércio": 1}
    assert report.fallback_by_segment == {"Consumo / Comércio / Varejo": 1}
    assert report.fallback_issuer_samples_by_subsector == {
        "Consumo / Comércio": ("RETL",)
    }
    assert report.fallback_issuer_samples_by_segment == {
        "Consumo / Comércio / Varejo": ("RETL",)
    }
    assert report.fallback_company_samples_by_segment == {
        "Consumo / Comércio / Varejo": (
            SectorCoverageCompanySample(issuer_code="RETL", company_id="cvm:3"),
        )
    }


def test_sector_coverage_bounds_and_sorts_fallback_samples() -> None:
    report = profile_sector_model_coverage(
        [
            _record("cvm:1", "ZZZZ", sector="Consumo", subsector="Comércio", segment="Varejo"),
            _record("cvm:2", "AAAA", sector="Consumo", subsector="Comércio", segment="Varejo"),
            _record("cvm:3", "MMMM", sector="Consumo", subsector="Comércio", segment="Atacado"),
        ],
        registry=_registry(),
        classification_rows=3,
        fallback_sample_limit=2,
    )

    assert report.fallback_issuer_samples_by_subsector == {
        "Consumo / Comércio": ("AAAA", "MMMM")
    }
    assert report.fallback_by_segment == {
        "Consumo / Comércio / Atacado": 1,
        "Consumo / Comércio / Varejo": 2,
    }
    assert report.fallback_issuer_samples_by_segment == {
        "Consumo / Comércio / Atacado": ("MMMM",),
        "Consumo / Comércio / Varejo": ("AAAA", "ZZZZ"),
    }
    assert report.fallback_company_samples_by_segment == {
        "Consumo / Comércio / Atacado": (
            SectorCoverageCompanySample(issuer_code="MMMM", company_id="cvm:3"),
        ),
        "Consumo / Comércio / Varejo": (
            SectorCoverageCompanySample(issuer_code="AAAA", company_id="cvm:2"),
            SectorCoverageCompanySample(issuer_code="ZZZZ", company_id="cvm:1"),
        ),
    }


def test_sector_coverage_keeps_unknown_outside_catalog_rows_unresolved() -> None:
    report = profile_sector_model_coverage(
        [_record("cvm:1", "BANK", sector="Financeiro", subsector="X", segment="Bancos")],
        registry=_registry(),
        classification_rows=3,
        outside_active_company_catalog_issuer_codes=("CEPAC", "MISSING"),
        verified_non_equity_issuer_codes=("CEPAC", "STALE"),
    )

    assert report.company_catalog_mapped_rows == 1
    assert report.verified_non_equity_exclusions == 1
    assert report.unresolved_outside_catalog_rows == 1
    assert report.equity_candidate_identity_coverage == 0.5
    assert report.verified_non_equity_issuer_codes == ("CEPAC",)
    assert report.unresolved_outside_catalog_issuer_codes == ("MISSING",)


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


def test_sector_coverage_rejects_negative_fallback_sample_limit() -> None:
    with pytest.raises(ValueError, match="fallback_sample_limit"):
        profile_sector_model_coverage(
            [],
            registry=_registry(),
            classification_rows=0,
            fallback_sample_limit=-1,
        )
