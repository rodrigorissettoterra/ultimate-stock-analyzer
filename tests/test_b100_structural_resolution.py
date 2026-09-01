from datetime import UTC, date, datetime
from pathlib import Path

from ultimate_stock_analyzer.domain.master import SectorClassificationRecord
from ultimate_stock_analyzer.scoring.applicability_review import (
    StructuralApplicabilityReview,
    StructuralApplicabilityReviewRegistry,
)
from ultimate_stock_analyzer.scoring.b100_accounting_lifecycle import (
    B100AccountingLifecycleReport,
    B100AccountingSnapshot,
)
from ultimate_stock_analyzer.scoring.b100_structural_resolution import (
    evaluate_b100_general_corporate_resolution,
)
from ultimate_stock_analyzer.scoring.sector_models import SectorModelRegistry


def _classification(company_id: str, cvm_code: int, issuer_code: str) -> SectorClassificationRecord:
    return SectorClassificationRecord(
        company_id=company_id,
        cvm_code=cvm_code,
        issuer_code=issuer_code,
        trading_name=issuer_code,
        sector="Financeiro",
        subsector="Serviços Diversos",
        segment="Serviços Diversos",
        listing_segment="Novo Mercado",
        collected_at=datetime(2026, 9, 1, tzinfo=UTC),
    )


def _snapshot(
    snapshot_id: str,
    *,
    document_type: str,
    fiscal_year: int,
    reference_date: date,
) -> B100AccountingSnapshot:
    return B100AccountingSnapshot(
        snapshot_id=snapshot_id,
        document_type=document_type,
        fiscal_year=fiscal_year,
        scope_token="con",
        consolidation_scope="DF Consolidado",
        reference_date=reference_date,
        line_count=100,
        general_corporate_critical_coverage=1.0,
        general_corporate_total_coverage=0.9,
        general_corporate_missing_critical=(),
        general_corporate_missing_supporting=("inventories_current",),
        holding_critical_schema_coverage=0.6,
        holding_total_schema_coverage=0.5,
        holding_exact_concepts=("total_assets", "equity", "net_income_parent"),
        holding_missing_concepts=("investments_total", "equity_method_result"),
        holding_label_mismatch_concepts=(),
        holding_ambiguous_concepts=(),
        total_assets=100.0,
        investments_total=0.0,
        equity=50.0,
        revenue=20.0,
        ebit=2.0,
        equity_method_result=None,
        net_income=1.0,
        cash_from_operations=3.0,
        investments_to_assets=0.0,
        equity_to_assets=0.5,
        equity_method_to_net_income=None,
        source_documents=("test.csv",),
    )


def test_b100_resolution_removes_review_without_changing_routing() -> None:
    root = Path(__file__).resolve().parents[1]
    registry = SectorModelRegistry.from_yaml(root / "config/scoring/sector_registry_v0.6.yml")
    prior = StructuralApplicabilityReviewRegistry(
        version="0.4",
        effect="diagnostic_only",
        reviews=(
            StructuralApplicabilityReview(
                company_id="cvm:27634",
                issuer_code="B100",
                status="GENERAL_CORPORATE_MODEL_REVIEW_REQUIRED",
                reason="test prior unresolved review",
                evidence_contracts=("CVM_CANONICAL_IDENTITY",),
            ),
        ),
    )
    current = StructuralApplicabilityReviewRegistry(
        version="0.5",
        effect="diagnostic_only",
        reviews=(),
    )
    lifecycle = B100AccountingLifecycleReport(
        company_id="cvm:27634",
        snapshot_count=2,
        evidence_snapshot_count=2,
        latest_reference_date=date(2026, 6, 30),
        general_corporate_full_critical_snapshot_ids=("DFP_2025_con", "ITR_2026_con"),
        holding_full_critical_schema_snapshot_ids=(),
        snapshots=(
            _snapshot(
                "DFP_2025_con",
                document_type="DFP",
                fiscal_year=2025,
                reference_date=date(2025, 12, 31),
            ),
            _snapshot(
                "ITR_2026_con",
                document_type="ITR",
                fiscal_year=2026,
                reference_date=date(2026, 6, 30),
            ),
        ),
    )

    report = evaluate_b100_general_corporate_resolution(
        [
            _classification("cvm:27634", 27634, "B100"),
            _classification("cvm:999", 999, "TEST"),
        ],
        registry=registry,
        prior_reviews=prior,
        current_reviews=current,
        lifecycle=lifecycle,
    )

    assert report.resolution_passed
    assert report.failures == ()
    assert report.b100_model_id == "general_corporate"
    assert report.b100_is_fallback is True
    assert report.routing_delta_company_ids == ()
    assert report.prior_reviewed_fallback_companies == 1
    assert report.current_reviewed_fallback_companies == 0
    assert report.current_review_company_ids == ()
