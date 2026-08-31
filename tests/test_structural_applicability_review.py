from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from ultimate_stock_analyzer.domain.master import SectorClassificationRecord
from ultimate_stock_analyzer.scoring.applicability_review import (
    StructuralApplicabilityReview,
    StructuralApplicabilityReviewRegistry,
    load_structural_applicability_reviews,
)
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
        ),
    )


def test_structural_review_registry_is_diagnostic_and_keyed_by_cvm_identity(
    tmp_path: Path,
) -> None:
    path = tmp_path / "reviews.json"
    path.write_text(
        json.dumps(
            {
                "version": "test",
                "effect": "diagnostic_only",
                "reviews": [
                    {
                        "company_id": "cvm:6041",
                        "issuer_code": "fige",
                        "status": "GENERAL_CORPORATE_MODEL_REVIEW_REQUIRED",
                        "reason": "Needs model review.",
                        "evidence_contracts": [
                            "b3_industry_classification",
                            "cvm_canonical_identity",
                        ],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    registry = load_structural_applicability_reviews(path)

    assert registry.version == "test"
    assert registry.effect == "diagnostic_only"
    assert registry.by_company_id["cvm:6041"].issuer_code == "FIGE"
    assert registry.by_company_id["cvm:6041"].evidence_contracts == (
        "B3_INDUSTRY_CLASSIFICATION",
        "CVM_CANONICAL_IDENTITY",
    )


def test_structural_review_registry_rejects_non_diagnostic_effect(tmp_path: Path) -> None:
    path = tmp_path / "reviews.json"
    path.write_text(
        json.dumps({"version": "test", "effect": "blocking", "reviews": []}),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="diagnostic_only"):
        load_structural_applicability_reviews(path)


def test_sector_coverage_reports_reviews_without_changing_model_routing() -> None:
    reviews = StructuralApplicabilityReviewRegistry(
        version="test",
        effect="diagnostic_only",
        reviews=(
            StructuralApplicabilityReview(
                company_id="cvm:1",
                issuer_code="BANK",
                status="GENERAL_CORPORATE_MODEL_REVIEW_REQUIRED",
                reason="Stale review should be visible after specialized routing.",
                evidence_contracts=("B3_INDUSTRY_CLASSIFICATION",),
            ),
            StructuralApplicabilityReview(
                company_id="cvm:2",
                issuer_code="HOLD",
                status="GENERAL_CORPORATE_MODEL_REVIEW_REQUIRED",
                reason="Fallback needs economic review.",
                evidence_contracts=("B3_INDUSTRY_CLASSIFICATION",),
            ),
            StructuralApplicabilityReview(
                company_id="cvm:3",
                issuer_code="BDRX",
                status="UNIVERSE_ELIGIBILITY_REVIEW_REQUIRED",
                reason="Universe contract is not final.",
                evidence_contracts=("CVM_FCA_SECURITY_MASTER",),
            ),
            StructuralApplicabilityReview(
                company_id="cvm:999",
                issuer_code="MISS",
                status="GENERAL_CORPORATE_MODEL_REVIEW_REQUIRED",
                reason="Missing current classification should stay visible.",
                evidence_contracts=("CVM_CANONICAL_IDENTITY",),
            ),
        ),
    )

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
                "HOLD",
                sector="Financeiro",
                subsector="Holdings",
                segment="Holdings Diversificadas",
            ),
            _record(
                "cvm:3",
                "BDRX",
                sector="Financeiro",
                subsector="Serviços Financeiros Diversos",
                segment="Outros",
            ),
        ],
        registry=_registry(),
        classification_rows=3,
        applicability_review_registry=reviews,
    )

    assert report.model_counts == {"banks": 1, "general_corporate": 2}
    assert report.specialized_companies == 1
    assert report.fallback_companies == 2
    assert report.applicability_review_version == "test"
    assert report.applicability_review_effect == "diagnostic_only"
    assert report.reviewed_fallback_companies == 2
    assert report.review_status_counts == {
        "GENERAL_CORPORATE_MODEL_REVIEW_REQUIRED": 1,
        "UNIVERSE_ELIGIBILITY_REVIEW_REQUIRED": 1,
    }
    assert report.review_company_ids_by_status == {
        "GENERAL_CORPORATE_MODEL_REVIEW_REQUIRED": ("cvm:2",),
        "UNIVERSE_ELIGIBILITY_REVIEW_REQUIRED": ("cvm:3",),
    }
    assert report.review_non_fallback_company_ids == ("cvm:1",)
    assert report.review_unmatched_company_ids == ("cvm:999",)
