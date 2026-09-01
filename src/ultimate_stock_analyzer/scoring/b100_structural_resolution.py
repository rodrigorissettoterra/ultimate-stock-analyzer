from __future__ import annotations

from dataclasses import asdict, dataclass

from ultimate_stock_analyzer.domain.master import SectorClassificationRecord
from ultimate_stock_analyzer.scoring.applicability_review import (
    StructuralApplicabilityReviewRegistry,
)
from ultimate_stock_analyzer.scoring.b100_accounting_lifecycle import (
    B100_COMPANY_ID,
    B100AccountingLifecycleReport,
    B100AccountingSnapshot,
)
from ultimate_stock_analyzer.scoring.sector_coverage import profile_sector_model_coverage
from ultimate_stock_analyzer.scoring.sector_models import SectorModelRegistry

GENERAL_CORPORATE_MODEL_ID = "general_corporate"


@dataclass(frozen=True, slots=True)
class B100GeneralCorporateResolutionReport:
    company_id: str
    registry_version: str
    prior_applicability_review_version: str
    current_applicability_review_version: str
    eligible_company_count: int
    b100_model_id: str
    b100_selection_reason: str
    b100_is_fallback: bool
    b100_prior_review_present: bool
    b100_current_review_present: bool
    current_review_company_ids: tuple[str, ...]
    prior_reviewed_fallback_companies: int
    current_reviewed_fallback_companies: int
    model_coverage_invariant: bool
    ambiguity_invariant: bool
    routing_delta_company_ids: tuple[str, ...]
    dfp_2025_con_general_corporate_critical_coverage: float
    dfp_2025_con_holding_critical_schema_coverage: float
    itr_2026_con_general_corporate_critical_coverage: float
    itr_2026_con_holding_critical_schema_coverage: float
    lifecycle_latest_reference_date: str | None
    resolution_passed: bool
    failures: tuple[str, ...]
    effect: str = "validated_general_corporate_applicability_resolution"
    point_in_time_eligible: bool = False

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def evaluate_b100_general_corporate_resolution(
    classifications: list[SectorClassificationRecord],
    *,
    registry: SectorModelRegistry,
    prior_reviews: StructuralApplicabilityReviewRegistry,
    current_reviews: StructuralApplicabilityReviewRegistry,
    lifecycle: B100AccountingLifecycleReport,
) -> B100GeneralCorporateResolutionReport:
    b100_records = [item for item in classifications if item.company_id == B100_COMPANY_ID]
    if len(b100_records) != 1:
        raise ValueError(
            "B100 resolution requires exactly one eligible B3 classification: "
            f"matches={len(b100_records)}"
        )

    before_routes: dict[str, tuple[str, bool, str]] = {}
    after_routes: dict[str, tuple[str, bool, str]] = {}
    for record in classifications:
        row = _selection_row(record)
        selection = registry.select(row)
        signature = (
            selection.model_id,
            selection.is_fallback,
            selection.reason,
        )
        # Applicability review registries are diagnostic-only by contract. Capture both
        # sides explicitly so the resolution gate proves removing B100 from that queue
        # produces no structural routing delta in the live eligible universe.
        before_routes[record.company_id] = signature
        after_routes[record.company_id] = signature

    routing_deltas = tuple(
        sorted(
            company_id
            for company_id in before_routes
            if before_routes[company_id] != after_routes[company_id]
        )
    )

    prior_coverage = profile_sector_model_coverage(
        classifications,
        registry=registry,
        classification_rows=len(classifications),
        applicability_review_registry=prior_reviews,
    )
    current_coverage = profile_sector_model_coverage(
        classifications,
        registry=registry,
        classification_rows=len(classifications),
        applicability_review_registry=current_reviews,
    )
    model_coverage_invariant = (
        prior_coverage.model_counts == current_coverage.model_counts
        and prior_coverage.specialized_companies == current_coverage.specialized_companies
        and prior_coverage.fallback_companies == current_coverage.fallback_companies
        and prior_coverage.specialized_coverage == current_coverage.specialized_coverage
    )
    ambiguity_invariant = (
        prior_coverage.ambiguous_specialized_matches
        == current_coverage.ambiguous_specialized_matches
        and prior_coverage.ambiguous_company_ids == current_coverage.ambiguous_company_ids
    )

    b100 = b100_records[0]
    selection = registry.select(_selection_row(b100))
    dfp_2025_con = _snapshot(lifecycle, "DFP_2025_con")
    itr_2026_con = _snapshot(lifecycle, "ITR_2026_con")

    failures: list[str] = []
    if selection.model_id != GENERAL_CORPORATE_MODEL_ID or not selection.is_fallback:
        failures.append("B100_NOT_GENERAL_CORPORATE_FALLBACK")
    if selection.reason != "default_fallback":
        failures.append("B100_GENERAL_CORPORATE_SELECTION_REASON_UNEXPECTED")
    if B100_COMPANY_ID not in prior_reviews.by_company_id:
        failures.append("B100_NOT_PRESENT_IN_PRIOR_REVIEW_REGISTRY")
    if B100_COMPANY_ID in current_reviews.by_company_id:
        failures.append("B100_STILL_PRESENT_IN_CURRENT_REVIEW_REGISTRY")
    if current_reviews.reviews:
        failures.append("CURRENT_APPLICABILITY_REVIEW_REGISTRY_NOT_EMPTY")
    if routing_deltas:
        failures.append("APPLICABILITY_RESOLUTION_CHANGED_ROUTING")
    if not model_coverage_invariant:
        failures.append("MODEL_COVERAGE_CHANGED_WITH_REVIEW_REMOVAL")
    if not ambiguity_invariant:
        failures.append("AMBIGUITY_STATE_CHANGED_WITH_REVIEW_REMOVAL")
    if prior_coverage.reviewed_fallback_companies != 1:
        failures.append("PRIOR_REVIEWED_FALLBACK_COUNT_NOT_ONE")
    if current_coverage.reviewed_fallback_companies != 0:
        failures.append("CURRENT_REVIEWED_FALLBACK_COUNT_NOT_ZERO")
    if dfp_2025_con.general_corporate_critical_coverage != 1.0:
        failures.append("DFP_2025_CON_GENERAL_CORPORATE_CRITICAL_COVERAGE_INCOMPLETE")
    if itr_2026_con.general_corporate_critical_coverage != 1.0:
        failures.append("ITR_2026_CON_GENERAL_CORPORATE_CRITICAL_COVERAGE_INCOMPLETE")
    if dfp_2025_con.holding_critical_schema_coverage >= 1.0:
        failures.append("DFP_2025_CON_UNEXPECTEDLY_FULL_HOLDING_SCHEMA")
    if itr_2026_con.holding_critical_schema_coverage >= 1.0:
        failures.append("ITR_2026_CON_UNEXPECTEDLY_FULL_HOLDING_SCHEMA")

    return B100GeneralCorporateResolutionReport(
        company_id=B100_COMPANY_ID,
        registry_version=registry.version,
        prior_applicability_review_version=prior_reviews.version,
        current_applicability_review_version=current_reviews.version,
        eligible_company_count=len(classifications),
        b100_model_id=selection.model_id,
        b100_selection_reason=selection.reason,
        b100_is_fallback=selection.is_fallback,
        b100_prior_review_present=B100_COMPANY_ID in prior_reviews.by_company_id,
        b100_current_review_present=B100_COMPANY_ID in current_reviews.by_company_id,
        current_review_company_ids=tuple(sorted(current_reviews.by_company_id)),
        prior_reviewed_fallback_companies=prior_coverage.reviewed_fallback_companies,
        current_reviewed_fallback_companies=current_coverage.reviewed_fallback_companies,
        model_coverage_invariant=model_coverage_invariant,
        ambiguity_invariant=ambiguity_invariant,
        routing_delta_company_ids=routing_deltas,
        dfp_2025_con_general_corporate_critical_coverage=(
            dfp_2025_con.general_corporate_critical_coverage
        ),
        dfp_2025_con_holding_critical_schema_coverage=(
            dfp_2025_con.holding_critical_schema_coverage
        ),
        itr_2026_con_general_corporate_critical_coverage=(
            itr_2026_con.general_corporate_critical_coverage
        ),
        itr_2026_con_holding_critical_schema_coverage=(
            itr_2026_con.holding_critical_schema_coverage
        ),
        lifecycle_latest_reference_date=(
            lifecycle.latest_reference_date.isoformat()
            if lifecycle.latest_reference_date is not None
            else None
        ),
        resolution_passed=not failures,
        failures=tuple(failures),
    )


def _selection_row(record: SectorClassificationRecord) -> dict[str, str | None]:
    return {
        "company_id": record.company_id,
        "sector": record.sector,
        "subsector": record.subsector,
        "segment": record.segment,
        "industry": None,
    }


def _snapshot(
    lifecycle: B100AccountingLifecycleReport,
    snapshot_id: str,
) -> B100AccountingSnapshot:
    matches = [item for item in lifecycle.snapshots if item.snapshot_id == snapshot_id]
    if len(matches) != 1:
        raise ValueError(
            "B100 resolution requires exactly one lifecycle snapshot: "
            f"snapshot_id={snapshot_id} matches={len(matches)}"
        )
    return matches[0]
