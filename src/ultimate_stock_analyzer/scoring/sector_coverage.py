from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from dataclasses import asdict, dataclass

from ultimate_stock_analyzer.domain.master import SectorClassificationRecord
from ultimate_stock_analyzer.scoring.sector_models import SectorModelRegistry


@dataclass(frozen=True, slots=True)
class SectorCoverageReport:
    classification_rows: int
    identity_mapped_rows: int
    identity_unmapped_rows: int
    identity_coverage: float
    normalized_companies: int
    model_counts: dict[str, int]
    specialized_companies: int
    fallback_companies: int
    specialized_coverage: float
    ambiguous_specialized_matches: int
    unmapped_issuer_codes: tuple[str, ...]
    ambiguous_company_ids: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def profile_sector_model_coverage(
    classifications: Iterable[SectorClassificationRecord],
    *,
    registry: SectorModelRegistry,
    classification_rows: int,
    unmapped_issuer_codes: Iterable[str] = (),
    sample_limit: int = 50,
) -> SectorCoverageReport:
    records = list(classifications)
    unmapped = tuple(
        sorted(
            {
                str(code).strip().upper()
                for code in unmapped_issuer_codes
                if str(code).strip()
            }
        )
    )
    if classification_rows < 0:
        raise ValueError("classification_rows must be non-negative")
    if len(unmapped) > classification_rows:
        raise ValueError("unmapped issuer count exceeds classification row count")
    if sample_limit < 0:
        raise ValueError("sample_limit must be non-negative")

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

    mapped_rows = classification_rows - len(unmapped)
    fallback = model_counts.get(registry.default_model.model_id, 0)
    specialized = len(records) - fallback
    return SectorCoverageReport(
        classification_rows=classification_rows,
        identity_mapped_rows=mapped_rows,
        identity_unmapped_rows=len(unmapped),
        identity_coverage=(
            mapped_rows / classification_rows if classification_rows else 0.0
        ),
        normalized_companies=len(records),
        model_counts=dict(sorted(model_counts.items())),
        specialized_companies=specialized,
        fallback_companies=fallback,
        specialized_coverage=(specialized / len(records) if records else 0.0),
        ambiguous_specialized_matches=len(ambiguous),
        unmapped_issuer_codes=unmapped[:sample_limit],
        ambiguous_company_ids=tuple(sorted(set(ambiguous)))[:sample_limit],
    )
