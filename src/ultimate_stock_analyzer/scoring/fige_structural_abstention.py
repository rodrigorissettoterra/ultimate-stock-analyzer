from __future__ import annotations

from dataclasses import asdict, dataclass

from ultimate_stock_analyzer.domain.master import SectorClassificationRecord
from ultimate_stock_analyzer.scoring.applicability_review import (
    StructuralApplicabilityReviewRegistry,
)
from ultimate_stock_analyzer.scoring.sector_models import (
    SectorModelRegistry,
    SectorStructuralScoringEngine,
)

FIGE_COMPANY_ID = "cvm:6041"
ABSTAIN_MODEL_ID = "financial_non_prudential_abstain"
ABSTAIN_MODEL_FAMILY = "financial_non_prudential_abstain_v1"


@dataclass(frozen=True, slots=True)
class FigeRoutingDelta:
    company_id: str
    issuer_code: str
    sector: str
    subsector: str
    segment: str
    before_model_id: str
    after_model_id: str
    before_is_fallback: bool
    after_is_fallback: bool


@dataclass(frozen=True, slots=True)
class FigeStructuralAbstentionRegressionReport:
    registry_version: str
    applicability_review_version: str
    eligible_company_count: int
    routing_deltas: tuple[FigeRoutingDelta, ...]
    abstention_company_ids: tuple[str, ...]
    ambiguous_specialized_company_ids: tuple[str, ...]
    fige_review_present: bool
    fige_model_id: str
    fige_model_family: str
    fige_structural_score: float
    fige_data_coverage: float
    fige_confidence: float
    fige_rankable: bool
    fige_categories: tuple[str, ...]
    fige_flags: tuple[str, ...]
    corporate_metric_probe_invariant: bool
    historical_backtest_executed: bool
    historical_backtest_reason: str
    regression_passed: bool
    failures: tuple[str, ...]
    effect: str = "validated_structural_abstention_routing"

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def evaluate_fige_structural_abstention(
    classifications: list[SectorClassificationRecord],
    *,
    registry: SectorModelRegistry,
    applicability_reviews: StructuralApplicabilityReviewRegistry,
) -> FigeStructuralAbstentionRegressionReport:
    baseline = _registry_without_abstention(registry)
    deltas: list[FigeRoutingDelta] = []
    abstention_ids: list[str] = []
    ambiguous_ids: list[str] = []

    fige_records = [item for item in classifications if item.company_id == FIGE_COMPANY_ID]
    if len(fige_records) != 1:
        raise ValueError(
            "FIGE structural abstention requires exactly one eligible B3 classification: "
            f"matches={len(fige_records)}"
        )

    for record in classifications:
        row = _selection_row(record)
        before = baseline.select(row)
        after = registry.select(row)
        if before.model_id != after.model_id:
            deltas.append(
                FigeRoutingDelta(
                    company_id=record.company_id,
                    issuer_code=record.issuer_code,
                    sector=record.sector,
                    subsector=record.subsector,
                    segment=record.segment,
                    before_model_id=before.model_id,
                    after_model_id=after.model_id,
                    before_is_fallback=before.is_fallback,
                    after_is_fallback=after.is_fallback,
                )
            )
        if after.model_id == ABSTAIN_MODEL_ID:
            abstention_ids.append(record.company_id)
        matches = [
            model.model_id
            for model in registry.models
            if model.match_reason(row) is not None
        ]
        if len(matches) > 1:
            ambiguous_ids.append(record.company_id)

    fige = fige_records[0]
    probe = _corporate_metric_probe(fige, scale=1.0)
    changed_probe = _corporate_metric_probe(fige, scale=999.0)
    engine = SectorStructuralScoringEngine(registry)
    first = engine.score_universe([probe])[0]
    changed = engine.score_universe([changed_probe])[0]
    invariant = (
        first.structural_score == changed.structural_score
        and first.data_coverage == changed.data_coverage
        and first.confidence == changed.confidence
        and first.rankable == changed.rankable
        and first.categories == changed.categories
        and first.flags == changed.flags
    )

    failures: list[str] = []
    if [delta.company_id for delta in deltas] != [FIGE_COMPANY_ID]:
        failures.append("ROUTING_DELTA_NOT_EXACTLY_FIGE")
    elif (
        deltas[0].before_model_id != registry.default_model.model_id
        or not deltas[0].before_is_fallback
        or deltas[0].after_model_id != ABSTAIN_MODEL_ID
        or deltas[0].after_is_fallback
    ):
        failures.append("FIGE_ROUTING_DELTA_UNEXPECTED")
    if tuple(sorted(abstention_ids)) != (FIGE_COMPANY_ID,):
        failures.append("ABSTENTION_MODEL_CURRENT_SCOPE_NOT_EXACTLY_FIGE")
    if ambiguous_ids:
        failures.append("AMBIGUOUS_SPECIALIZED_MODEL_MATCH")
    fige_review_present = FIGE_COMPANY_ID in applicability_reviews.by_company_id
    if fige_review_present:
        failures.append("FIGE_STILL_IN_APPLICABILITY_REVIEW_REGISTRY")
    if first.model_id != ABSTAIN_MODEL_ID:
        failures.append("FIGE_NOT_SCORED_BY_ABSTENTION_MODEL")
    if first.model_family != ABSTAIN_MODEL_FAMILY:
        failures.append("FIGE_ABSTENTION_MODEL_FAMILY_MISMATCH")
    if first.structural_score != 50.0:
        failures.append("FIGE_ABSTENTION_SCORE_NOT_NEUTRAL")
    if first.data_coverage != 0.0 or first.confidence != 0.0:
        failures.append("FIGE_ABSTENTION_EVIDENCE_NOT_ZERO")
    if first.rankable:
        failures.append("FIGE_ABSTENTION_UNEXPECTEDLY_RANKABLE")
    if first.categories:
        failures.append("FIGE_ABSTENTION_HAS_SCORE_CATEGORIES")
    required_flags = {
        "LOW_STRUCTURAL_DATA_COVERAGE",
        "LOW_STRUCTURAL_CONFIDENCE",
        "NO_STRUCTURAL_DATA",
    }
    if not required_flags.issubset(first.flags):
        failures.append("FIGE_ABSTENTION_FLAGS_INCOMPLETE")
    if not invariant:
        failures.append("FIGE_ABSTENTION_RESPONDS_TO_CORPORATE_METRICS")

    return FigeStructuralAbstentionRegressionReport(
        registry_version=registry.version,
        applicability_review_version=applicability_reviews.version,
        eligible_company_count=len(classifications),
        routing_deltas=tuple(deltas),
        abstention_company_ids=tuple(sorted(abstention_ids)),
        ambiguous_specialized_company_ids=tuple(sorted(ambiguous_ids)),
        fige_review_present=fige_review_present,
        fige_model_id=first.model_id,
        fige_model_family=first.model_family,
        fige_structural_score=first.structural_score,
        fige_data_coverage=first.data_coverage,
        fige_confidence=first.confidence,
        fige_rankable=first.rankable,
        fige_categories=tuple(sorted(first.categories)),
        fige_flags=first.flags,
        corporate_metric_probe_invariant=invariant,
        historical_backtest_executed=False,
        historical_backtest_reason=(
            "Current B3 industry classification is not point-in-time eligible; applying "
            "today's segment routing retroactively would create look-ahead bias."
        ),
        regression_passed=not failures,
        failures=tuple(failures),
    )


def _registry_without_abstention(registry: SectorModelRegistry) -> SectorModelRegistry:
    models = tuple(
        model for model in registry.models if model.model_id != ABSTAIN_MODEL_ID
    )
    if len(models) == len(registry.models):
        raise ValueError(
            f"Sector registry does not contain required model: {ABSTAIN_MODEL_ID}"
        )
    return SectorModelRegistry(
        version=f"{registry.version}-pre-abstention",
        default_model=registry.default_model,
        models=models,
    )


def _selection_row(record: SectorClassificationRecord) -> dict[str, str | None]:
    return {
        "sector": record.sector,
        "subsector": record.subsector,
        "segment": record.segment,
        "industry": None,
    }


def _corporate_metric_probe(
    record: SectorClassificationRecord,
    *,
    scale: float,
) -> dict[str, float | str]:
    return {
        "ticker": "FIGE3",
        "sector": record.sector,
        "subsector": record.subsector,
        "segment": record.segment,
        "roic": 0.10 * scale,
        "roe": 0.12 * scale,
        "roa": 0.06 * scale,
        "ebit_margin": 0.10 * scale,
        "net_margin": 0.07 * scale,
        "net_debt_ebitda": 3.0 * scale,
        "interest_coverage": 3.0 * scale,
        "debt_to_equity": 1.5 * scale,
        "equity_ratio": 0.30 * scale,
        "cash_to_debt": 0.20 * scale,
        "cash_conversion": 1.0 * scale,
        "fcf_margin": 0.08 * scale,
        "cfo_margin": 0.10 * scale,
        "operating_cash_flow_to_debt": 0.20 * scale,
        "revenue_cagr_5y": 0.05 * scale,
        "net_income_cagr_5y": 0.04 * scale,
        "fcf_cagr_5y": 0.04 * scale,
        "dividend_regularity": 60.0 * scale,
        "dividend_sustainability": 55.0 * scale,
        "dividend_cagr_5y": 0.03 * scale,
    }
