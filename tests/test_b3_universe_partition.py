from datetime import UTC, datetime

import pytest

from ultimate_stock_analyzer.domain.master import SectorClassificationRecord
from ultimate_stock_analyzer.universe.b3_partition import (
    partition_current_b3_classifications,
)
from ultimate_stock_analyzer.universe.eligibility import (
    BrazilianEquityEligibilityDecision,
    BrazilianEquityEligibilityReport,
    classify_brazilian_equity_issuers,
)


def _classification(company_id: str, issuer_code: str) -> SectorClassificationRecord:
    return SectorClassificationRecord(
        company_id=company_id,
        cvm_code=int(company_id.split(":", 1)[1]),
        issuer_code=issuer_code,
        trading_name=issuer_code,
        sector="Financeiro",
        subsector="Serviços Financeiros Diversos",
        segment="Serviços Financeiros Diversos",
        collected_at=datetime(2026, 8, 31, tzinfo=UTC),
    )


def test_b3_partition_preserves_audit_statuses_and_returns_only_eligible_records() -> None:
    records = [
        _classification("cvm:9512", "PETR"),
        _classification("cvm:80152", "PPLA"),
        _classification("cvm:99999", "MISS"),
    ]
    eligibility = classify_brazilian_equity_issuers(
        (record.company_id for record in records),
        brazilian_public_company_ids=("cvm:9512",),
        foreign_issuer_company_ids=("cvm:80152",),
    )

    eligible, report = partition_current_b3_classifications(
        records,
        eligibility_report=eligibility,
    )

    assert [record.company_id for record in eligible] == ["cvm:9512"]
    assert report.classification_records == 3
    assert report.eligible_brazilian_company_equities == 1
    assert report.excluded_foreign_issuers == 1
    assert report.unresolved_registry_classifications == 1
    assert report.conflicting_registry_classifications == 0
    assert report.excluded_foreign_samples[0].company_id == "cvm:80152"
    assert report.unresolved_samples[0].company_id == "cvm:99999"


def test_b3_partition_exposes_conflicts() -> None:
    record = _classification("cvm:123", "TEST")
    eligibility = classify_brazilian_equity_issuers(
        (record.company_id,),
        brazilian_public_company_ids=("cvm:123",),
        foreign_issuer_company_ids=("cvm:123",),
    )

    eligible, report = partition_current_b3_classifications(
        (record,),
        eligibility_report=eligibility,
    )

    assert eligible == []
    assert report.conflicting_registry_classifications == 1
    assert report.conflicting_samples[0].company_id == "cvm:123"


def test_b3_partition_rejects_missing_eligibility_decision() -> None:
    empty_report = BrazilianEquityEligibilityReport(
        decisions=(),
        status_counts={},
        eligible_company_ids=(),
        excluded_foreign_company_ids=(),
        unresolved_company_ids=(),
        conflicting_company_ids=(),
    )

    with pytest.raises(ValueError, match="lack universe eligibility decisions"):
        partition_current_b3_classifications(
            (_classification("cvm:9512", "PETR"),),
            eligibility_report=empty_report,
        )


def test_b3_partition_sample_limit_is_deterministic() -> None:
    records = [
        _classification("cvm:80195", "G2DI"),
        _classification("cvm:80152", "PPLA"),
    ]
    decisions = (
        BrazilianEquityEligibilityDecision(
            company_id="cvm:80195",
            status="EXCLUDED_FOREIGN_ISSUER",
            eligible=False,
            evidence_sources=("CVM_FOREIGN_ISSUER_CAD",),
            reason="foreign",
        ),
        BrazilianEquityEligibilityDecision(
            company_id="cvm:80152",
            status="EXCLUDED_FOREIGN_ISSUER",
            eligible=False,
            evidence_sources=("CVM_FOREIGN_ISSUER_CAD",),
            reason="foreign",
        ),
    )
    eligibility = BrazilianEquityEligibilityReport(
        decisions=decisions,
        status_counts={"EXCLUDED_FOREIGN_ISSUER": 2},
        eligible_company_ids=(),
        excluded_foreign_company_ids=("cvm:80152", "cvm:80195"),
        unresolved_company_ids=(),
        conflicting_company_ids=(),
    )

    _, report = partition_current_b3_classifications(
        records,
        eligibility_report=eligibility,
        sample_limit=1,
    )

    assert len(report.excluded_foreign_samples) == 1
    assert report.excluded_foreign_samples[0].issuer_code == "G2DI"
