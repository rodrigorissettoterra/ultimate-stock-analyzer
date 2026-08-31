from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Iterable
from dataclasses import asdict, dataclass

from ultimate_stock_analyzer.domain.master import SectorClassificationRecord
from ultimate_stock_analyzer.universe.eligibility import (
    BrazilianEquityEligibilityReport,
)


@dataclass(frozen=True, slots=True, order=True)
class B3UniversePartitionSample:
    issuer_code: str
    company_id: str


@dataclass(frozen=True, slots=True)
class CurrentB3UniversePartitionReport:
    classification_records: int
    status_counts: dict[str, int]
    eligible_brazilian_company_equities: int
    excluded_foreign_issuers: int
    unresolved_registry_classifications: int
    conflicting_registry_classifications: int
    excluded_foreign_samples: tuple[B3UniversePartitionSample, ...]
    unresolved_samples: tuple[B3UniversePartitionSample, ...]
    conflicting_samples: tuple[B3UniversePartitionSample, ...]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def partition_current_b3_classifications(
    classifications: Iterable[SectorClassificationRecord],
    *,
    eligibility_report: BrazilianEquityEligibilityReport,
    sample_limit: int = 50,
) -> tuple[list[SectorClassificationRecord], CurrentB3UniversePartitionReport]:
    if sample_limit < 0:
        raise ValueError("sample_limit must be non-negative")

    records = list(classifications)
    decisions = {
        decision.company_id: decision for decision in eligibility_report.decisions
    }
    missing_decisions = sorted(
        {record.company_id for record in records} - decisions.keys()
    )
    if missing_decisions:
        raise ValueError(
            "B3 classification records lack universe eligibility decisions: "
            + ", ".join(missing_decisions[:10])
        )

    eligible: list[SectorClassificationRecord] = []
    counts: Counter[str] = Counter()
    samples: defaultdict[str, set[B3UniversePartitionSample]] = defaultdict(set)
    for record in records:
        decision = decisions[record.company_id]
        counts[decision.status] += 1
        if decision.eligible:
            eligible.append(record)
            continue
        samples[decision.status].add(
            B3UniversePartitionSample(
                issuer_code=str(record.issuer_code or "").strip().upper(),
                company_id=record.company_id,
            )
        )

    eligible.sort(key=lambda record: (record.company_id, record.issuer_code))
    return eligible, CurrentB3UniversePartitionReport(
        classification_records=len(records),
        status_counts=dict(sorted(counts.items())),
        eligible_brazilian_company_equities=counts.get(
            "ELIGIBLE_BRAZILIAN_PUBLIC_COMPANY", 0
        ),
        excluded_foreign_issuers=counts.get("EXCLUDED_FOREIGN_ISSUER", 0),
        unresolved_registry_classifications=counts.get(
            "UNRESOLVED_CVM_REGISTRY_CLASSIFICATION", 0
        ),
        conflicting_registry_classifications=counts.get(
            "CONFLICTING_CVM_REGISTRY_CLASSIFICATION", 0
        ),
        excluded_foreign_samples=tuple(
            sorted(samples["EXCLUDED_FOREIGN_ISSUER"])
        )[:sample_limit],
        unresolved_samples=tuple(
            sorted(samples["UNRESOLVED_CVM_REGISTRY_CLASSIFICATION"])
        )[:sample_limit],
        conflicting_samples=tuple(
            sorted(samples["CONFLICTING_CVM_REGISTRY_CLASSIFICATION"])
        )[:sample_limit],
    )
