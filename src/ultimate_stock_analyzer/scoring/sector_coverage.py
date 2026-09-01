from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Iterable
from dataclasses import asdict, dataclass

from ultimate_stock_analyzer.domain.master import SectorClassificationRecord
from ultimate_stock_analyzer.scoring.applicability_review import (
    StructuralApplicabilityReviewRegistry,
)
from ultimate_stock_analyzer.scoring.sector_models import SectorModelRegistry


@dataclass(frozen=True, slots=True, order=True)
class SectorCoverageCompanySample:
    issuer_code: str
    company_id: str


@dataclass(frozen=True, slots=True)
class SectorCoverageReport:
    classification_rows: int
    company_catalog_mapped_rows: int
    company_catalog_unmapped_rows: int
    company_catalog_join_coverage: float
    verified_non_equity_exclusions: int
    unresolved_outside_catalog_rows: int
    equity_candidate_identity_coverage: float
    normalized_companies: int
    model_counts: dict[str, int]
    specialized_companies: int
    fallback_companies: int
    specialized_coverage: float
    fallback_by_sector: dict[str, int]
    fallback_by_subsector: dict[str, int]
    fallback_by_segment: dict[str, int]
    fallback_issuer_samples_by_subsector: dict[str, tuple[str, ...]]
    fallback_issuer_samples_by_segment: dict[str, tuple[str, ...]]
    fallback_company_samples_by_segment: dict[
        str, tuple[SectorCoverageCompanySample, ...]
    ]
    applicability_review_version: str | None
    applicability_review_effect: str | None
    reviewed_fallback_companies: int
    review_status_counts: dict[str, int]
    review_company_ids_by_status: dict[str, tuple[str, ...]]
    review_non_fallback_company_ids: tuple[str, ...]
    review_unmatched_company_ids: tuple[str, ...]
    ambiguous_specialized_matches: int
    outside_active_company_catalog_issuer_codes: tuple[str, ...]
    verified_non_equity_issuer_codes: tuple[str, ...]
    unresolved_outside_catalog_issuer_codes: tuple[str, ...]
    ambiguous_company_ids: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _normalized_codes(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(
        sorted(
            {
                str(code).strip().upper()
                for code in values
                if str(code).strip()
            }
        )
    )


def profile_sector_model_coverage(
    classifications: Iterable[SectorClassificationRecord],
    *,
    registry: SectorModelRegistry,
    classification_rows: int,
    outside_active_company_catalog_issuer_codes: Iterable[str] = (),
    verified_non_equity_issuer_codes: Iterable[str] = (),
    applicability_review_registry: StructuralApplicabilityReviewRegistry | None = None,
    sample_limit: int = 50,
    fallback_sample_limit: int = 5,
) -> SectorCoverageReport:
    records = list(classifications)
    outside_catalog = _normalized_codes(outside_active_company_catalog_issuer_codes)
    verified_reference = set(_normalized_codes(verified_non_equity_issuer_codes))
    verified_exclusions = tuple(
        code for code in outside_catalog if code in verified_reference
    )
    unresolved_outside_catalog = tuple(
        code for code in outside_catalog if code not in verified_reference
    )

    if classification_rows < 0:
        raise ValueError("classification_rows must be non-negative")
    if len(outside_catalog) > classification_rows:
        raise ValueError("outside-catalog issuer count exceeds classification row count")
    if sample_limit < 0:
        raise ValueError("sample_limit must be non-negative")
    if fallback_sample_limit < 0:
        raise ValueError("fallback_sample_limit must be non-negative")

    review_by_company = (
        applicability_review_registry.by_company_id
        if applicability_review_registry is not None
        else {}
    )
    model_counts: Counter[str] = Counter()
    fallback_by_sector: Counter[str] = Counter()
    fallback_by_subsector: Counter[str] = Counter()
    fallback_by_segment: Counter[str] = Counter()
    fallback_issuer_codes_by_subsector: defaultdict[str, set[str]] = defaultdict(set)
    fallback_issuer_codes_by_segment: defaultdict[str, set[str]] = defaultdict(set)
    fallback_companies_by_segment: defaultdict[
        str, set[SectorCoverageCompanySample]
    ] = defaultdict(set)
    review_status_counts: Counter[str] = Counter()
    review_company_ids_by_status: defaultdict[str, set[str]] = defaultdict(set)
    normalized_company_ids: set[str] = set()
    fallback_company_ids: set[str] = set()
    ambiguous: list[str] = []
    for record in records:
        normalized_company_ids.add(record.company_id)
        row = {
            "company_id": record.company_id,
            "sector": record.sector,
            "subsector": record.subsector,
            "segment": record.segment,
            "industry": None,
        }
        selection = registry.select(row)
        model_counts[selection.model_id] += 1
        if selection.model_id == registry.default_model.model_id:
            fallback_company_ids.add(record.company_id)
            subsector_key = f"{record.sector} / {record.subsector}"
            segment_key = f"{record.sector} / {record.subsector} / {record.segment}"
            fallback_by_sector[record.sector] += 1
            fallback_by_subsector[subsector_key] += 1
            fallback_by_segment[segment_key] += 1
            issuer_code = str(record.issuer_code or "").strip().upper()
            if issuer_code:
                fallback_issuer_codes_by_subsector[subsector_key].add(issuer_code)
                fallback_issuer_codes_by_segment[segment_key].add(issuer_code)
                fallback_companies_by_segment[segment_key].add(
                    SectorCoverageCompanySample(
                        issuer_code=issuer_code,
                        company_id=record.company_id,
                    )
                )
            review = review_by_company.get(record.company_id)
            if review is not None:
                review_status_counts[review.status] += 1
                review_company_ids_by_status[review.status].add(record.company_id)
        matches = [
            model.model_id
            for model in registry.models
            if model.match_reason(row) is not None
        ]
        if len(matches) > 1:
            ambiguous.append(record.company_id)

    mapped_rows = classification_rows - len(outside_catalog)
    equity_candidate_rows = classification_rows - len(verified_exclusions)
    fallback = model_counts.get(registry.default_model.model_id, 0)
    specialized = len(records) - fallback
    fallback_subsector_samples = {
        key: tuple(sorted(codes))[:fallback_sample_limit]
        for key, codes in sorted(fallback_issuer_codes_by_subsector.items())
    }
    fallback_segment_samples = {
        key: tuple(sorted(codes))[:fallback_sample_limit]
        for key, codes in sorted(fallback_issuer_codes_by_segment.items())
    }
    fallback_company_samples = {
        key: tuple(sorted(companies))[:fallback_sample_limit]
        for key, companies in sorted(fallback_companies_by_segment.items())
    }
    reviewed_company_ids = set(review_by_company)
    review_non_fallback = tuple(
        sorted((reviewed_company_ids & normalized_company_ids) - fallback_company_ids)
    )
    review_unmatched = tuple(sorted(reviewed_company_ids - normalized_company_ids))
    return SectorCoverageReport(
        classification_rows=classification_rows,
        company_catalog_mapped_rows=mapped_rows,
        company_catalog_unmapped_rows=len(outside_catalog),
        company_catalog_join_coverage=(
            mapped_rows / classification_rows if classification_rows else 0.0
        ),
        verified_non_equity_exclusions=len(verified_exclusions),
        unresolved_outside_catalog_rows=len(unresolved_outside_catalog),
        equity_candidate_identity_coverage=(
            mapped_rows / equity_candidate_rows if equity_candidate_rows else 0.0
        ),
        normalized_companies=len(records),
        model_counts=dict(sorted(model_counts.items())),
        specialized_companies=specialized,
        fallback_companies=fallback,
        specialized_coverage=(specialized / len(records) if records else 0.0),
        fallback_by_sector=dict(sorted(fallback_by_sector.items())),
        fallback_by_subsector=dict(sorted(fallback_by_subsector.items())),
        fallback_by_segment=dict(sorted(fallback_by_segment.items())),
        fallback_issuer_samples_by_subsector=fallback_subsector_samples,
        fallback_issuer_samples_by_segment=fallback_segment_samples,
        fallback_company_samples_by_segment=fallback_company_samples,
        applicability_review_version=(
            applicability_review_registry.version
            if applicability_review_registry is not None
            else None
        ),
        applicability_review_effect=(
            applicability_review_registry.effect
            if applicability_review_registry is not None
            else None
        ),
        reviewed_fallback_companies=sum(review_status_counts.values()),
        review_status_counts=dict(sorted(review_status_counts.items())),
        review_company_ids_by_status={
            key: tuple(sorted(company_ids))[:sample_limit]
            for key, company_ids in sorted(review_company_ids_by_status.items())
        },
        review_non_fallback_company_ids=review_non_fallback[:sample_limit],
        review_unmatched_company_ids=review_unmatched[:sample_limit],
        ambiguous_specialized_matches=len(ambiguous),
        outside_active_company_catalog_issuer_codes=outside_catalog[:sample_limit],
        verified_non_equity_issuer_codes=verified_exclusions[:sample_limit],
        unresolved_outside_catalog_issuer_codes=(
            unresolved_outside_catalog[:sample_limit]
        ),
        ambiguous_company_ids=tuple(sorted(set(ambiguous)))[:sample_limit],
    )
