from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from dataclasses import asdict, dataclass

from ultimate_stock_analyzer.domain.master import SectorClassificationRecord
from ultimate_stock_analyzer.scoring.sector_models import SectorModelRegistry


@dataclass(frozen=True, slots=True)
class SectorCoverageReport:
    classification_rows: int
    active_catalog_issuers: int
    classified_active_catalog_issuers: int
    active_catalog_unclassified_issuers: int
    active_catalog_classification_coverage: float
    classification_rows_outside_active_catalog: int
    normalized_companies: int
    model_counts: dict[str, int]
    specialized_companies: int
    fallback_companies: int
    specialized_coverage: float
    ambiguous_specialized_matches: int
    outside_active_catalog_issuer_codes: tuple[str, ...]
    unclassified_active_catalog_issuer_codes: tuple[str, ...]
    ambiguous_company_ids: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def profile_sector_model_coverage(
    classifications: Iterable[SectorClassificationRecord],
    *,
    registry: SectorModelRegistry,
    classification_issuer_codes: Iterable[str],
    active_catalog_issuer_codes: Iterable[str],
    sample_limit: int = 50,
) -> SectorCoverageReport:
    records = list(classifications)
    classified_codes = _issuer_code_set(classification_issuer_codes)
    active_codes = _issuer_code_set(active_catalog_issuer_codes)
    if sample_limit < 0:
        raise ValueError("sample_limit must be non-negative")

    classified_active = classified_codes & active_codes
    outside_catalog = classified_codes - active_codes
    unclassified_active = active_codes - classified_codes

    normalized_codes = {record.issuer_code.strip().upper() for record in records}
    if not normalized_codes <= classified_active:
        unexpected = sorted(normalized_codes - classified_active)
        raise ValueError(
            "normalized classifications contain issuer codes outside the exact "
            f"workbook/catalog intersection: {unexpected[:5]}"
        )

    model_counts: Counter[str] = Counter()
    ambiguous: list[str] = []
    for record in records:
        row = {
            "sector": record.sector,
            "subsector": record.subsector,
            "segment": record.segment,
            "industry": None,
        }
        selection = registry.select(row)
        model_counts[selection.model_id] += 1
        matches = [
            model.model_id
            for model in registry.models
            if model.match_reason(row) is not None
        ]
        if len(matches) > 1:
            ambiguous.append(record.company_id)

    fallback = model_counts.get(registry.default_model.model_id, 0)
    specialized = len(records) - fallback
    return SectorCoverageReport(
        classification_rows=len(classified_codes),
        active_catalog_issuers=len(active_codes),
        classified_active_catalog_issuers=len(classified_active),
        active_catalog_unclassified_issuers=len(unclassified_active),
        active_catalog_classification_coverage=(
            len(classified_active) / len(active_codes) if active_codes else 0.0
        ),
        classification_rows_outside_active_catalog=len(outside_catalog),
        normalized_companies=len(records),
        model_counts=dict(sorted(model_counts.items())),
        specialized_companies=specialized,
        fallback_companies=fallback,
        specialized_coverage=(specialized / len(records) if records else 0.0),
        ambiguous_specialized_matches=len(ambiguous),
        outside_active_catalog_issuer_codes=tuple(sorted(outside_catalog))[:sample_limit],
        unclassified_active_catalog_issuer_codes=tuple(sorted(unclassified_active))[
            :sample_limit
        ],
        ambiguous_company_ids=tuple(sorted(set(ambiguous)))[:sample_limit],
    )


def _issuer_code_set(values: Iterable[str]) -> set[str]:
    return {
        str(value).strip().upper()
        for value in values
        if str(value).strip()
    }
