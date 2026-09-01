from pathlib import Path

from ultimate_stock_analyzer.scoring.applicability_review import (
    load_structural_applicability_reviews,
)


def test_current_structural_applicability_registry_has_no_unresolved_model_cases() -> None:
    root = Path(__file__).resolve().parents[1]
    registry = load_structural_applicability_reviews(
        root / "config/universe/b3_structural_applicability_reviews_v0.5.json"
    )

    assert registry.version == "0.5"
    assert registry.effect == "diagnostic_only"
    assert registry.reviews == ()
    assert registry.by_company_id == {}

    assert "cvm:27634" not in registry.by_company_id  # B100: general_corporate resolved
    assert "cvm:7617" not in registry.by_company_id  # ITSA: issuer-specific abstention
    assert "cvm:6041" not in registry.by_company_id  # FIGE: explicit structural abstention
    assert "cvm:18759" not in registry.by_company_id  # BSCS: security-universe resolved
    assert "cvm:80195" not in registry.by_company_id  # G2DI: foreign issuer resolved
    assert "cvm:80152" not in registry.by_company_id  # PPLA: foreign issuer resolved
