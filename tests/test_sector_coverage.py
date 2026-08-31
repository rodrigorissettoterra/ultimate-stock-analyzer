from datetime import UTC, datetime

from ultimate_stock_analyzer.domain.master import SectorClassificationRecord
from ultimate_stock_analyzer.scoring.sector_coverage import profile_sector_model_coverage
from ultimate_stock_analyzer.scoring.sector_models import (
    SectorModelDefinition,
    SectorModelRegistry,
)


def _record(company_id: str, *, sector: str, subsector: str, segment: str) -> SectorClassificationRecord:
    return SectorClassificationRecord(
        company_id=company_id,
        cvm_code=company_id.split(":", 1)[1],
        cnpj="33000167000101",
        issuer_code=company_id[-4:].upper(),
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


def test_sector_coverage_profiles_identity_and_model_assignment() -> None:
    report = profile_sector_model_coverage(
        [
            _record("cvm:1", sector="Financeiro", subsector="Intermediários Financeiros", segment="Bancos"),
            _record("cvm:2", sector="Utilidade Pública", subsector="Energia Elétrica", segment="Energia Elétrica"),
            _record("cvm:3", sector="Consumo", subsector="Comércio", segment="Varejo"),
        ],
        registry=_registry(),
        classification_rows=4,
        unmapped_issuer_codes=("ABCD",),
    )

    assert report.identity_coverage == 0.75
    assert report.normalized_companies == 3
    assert report.model_counts == {"banks": 1, "general_corporate": 1, "utilities": 1}
    assert report.specialized_companies == 2
    assert report.fallback_companies == 1
    assert report.specialized_coverage == 2 / 3
    assert report.unmapped_issuer_codes == ("ABCD",)


def test_sector_coverage_reports_overlapping_specialized_rules() -> None:
    report = profile_sector_model_coverage(
        [
            _record("cvm:2", sector="Utilidade Pública", subsector="Energia Elétrica", segment="Energia Elétrica"),
        ],
        registry=_registry(),
        classification_rows=1,
    )
    # One model may match more than one field without being ambiguous across models.
    assert report.ambiguous_specialized_matches == 0


def test_sector_coverage_fails_on_impossible_denominator() -> None:
    try:
        profile_sector_model_coverage(
            [],
            registry=_registry(),
            classification_rows=0,
            unmapped_issuer_codes=("ABCD",),
        )
    except ValueError as exc:
        assert "exceeds" in str(exc)
    else:
        raise AssertionError("expected ValueError")
