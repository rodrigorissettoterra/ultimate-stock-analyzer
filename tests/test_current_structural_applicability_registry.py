from pathlib import Path

from ultimate_stock_analyzer.scoring.applicability_review import (
    load_structural_applicability_reviews,
)


def test_current_structural_applicability_registry_contains_only_unresolved_model_cases() -> None:
    root = Path(__file__).resolve().parents[1]
    registry = load_structural_applicability_reviews(
        root / "config/universe/b3_structural_applicability_reviews_v0.2.json"
    )

    assert registry.version == "0.2"
    assert registry.effect == "diagnostic_only"
    assert set(registry.by_company_id) == {"cvm:6041", "cvm:7617", "cvm:27634"}
    assert {
        review.status for review in registry.reviews
    } == {"GENERAL_CORPORATE_MODEL_REVIEW_REQUIRED"}

    assert "cvm:18759" not in registry.by_company_id  # BSCS: security-universe resolved
    assert "cvm:80195" not in registry.by_company_id  # G2DI: foreign issuer resolved
    assert "cvm:80152" not in registry.by_company_id  # PPLA: foreign issuer resolved
