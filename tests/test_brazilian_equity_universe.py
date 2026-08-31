import pytest

from ultimate_stock_analyzer.universe.eligibility import classify_brazilian_equity_issuers


def test_brazilian_equity_universe_separates_domestic_foreign_and_unresolved() -> None:
    report = classify_brazilian_equity_issuers(
        ("cvm:9512", "cvm:80152", "cvm:99999"),
        brazilian_public_company_ids=("cvm:9512",),
        foreign_issuer_company_ids=("cvm:80152",),
    )

    assert report.status_counts == {
        "ELIGIBLE_BRAZILIAN_PUBLIC_COMPANY": 1,
        "EXCLUDED_FOREIGN_ISSUER": 1,
        "UNRESOLVED_CVM_REGISTRY_CLASSIFICATION": 1,
    }
    assert report.eligible_company_ids == ("cvm:9512",)
    assert report.excluded_foreign_company_ids == ("cvm:80152",)
    assert report.unresolved_company_ids == ("cvm:99999",)


def test_brazilian_equity_universe_fails_closed_on_registry_conflict() -> None:
    report = classify_brazilian_equity_issuers(
        ("cvm:123",),
        brazilian_public_company_ids=("cvm:123",),
        foreign_issuer_company_ids=("cvm:123",),
    )

    decision = report.decisions[0]
    assert decision.status == "CONFLICTING_CVM_REGISTRY_CLASSIFICATION"
    assert decision.eligible is False
    assert decision.evidence_sources == ("CVM_CAD", "CVM_FOREIGN_ISSUER_CAD")


def test_brazilian_equity_universe_rejects_noncanonical_identity() -> None:
    with pytest.raises(ValueError, match="cvm:<CD_CVM>"):
        classify_brazilian_equity_issuers(
            ("PETR4",),
            brazilian_public_company_ids=(),
            foreign_issuer_company_ids=(),
        )
