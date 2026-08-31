from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from typing import Literal

BrazilianEquityEligibilityStatus = Literal[
    "ELIGIBLE_BRAZILIAN_PUBLIC_COMPANY",
    "EXCLUDED_FOREIGN_ISSUER",
    "CONFLICTING_CVM_REGISTRY_CLASSIFICATION",
    "UNRESOLVED_CVM_REGISTRY_CLASSIFICATION",
]


@dataclass(frozen=True, slots=True, order=True)
class BrazilianEquityEligibilityDecision:
    company_id: str
    status: BrazilianEquityEligibilityStatus
    eligible: bool
    evidence_sources: tuple[str, ...]
    reason: str


@dataclass(frozen=True, slots=True)
class BrazilianEquityEligibilityReport:
    decisions: tuple[BrazilianEquityEligibilityDecision, ...]
    status_counts: dict[str, int]
    eligible_company_ids: tuple[str, ...]
    excluded_foreign_company_ids: tuple[str, ...]
    unresolved_company_ids: tuple[str, ...]
    conflicting_company_ids: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def classify_brazilian_equity_issuers(
    candidate_company_ids: Iterable[str],
    *,
    brazilian_public_company_ids: Iterable[str],
    foreign_issuer_company_ids: Iterable[str],
) -> BrazilianEquityEligibilityReport:
    candidates = _canonical_company_ids(candidate_company_ids)
    brazilian = set(_canonical_company_ids(brazilian_public_company_ids))
    foreign = set(_canonical_company_ids(foreign_issuer_company_ids))

    decisions: list[BrazilianEquityEligibilityDecision] = []
    for company_id in candidates:
        in_brazilian = company_id in brazilian
        in_foreign = company_id in foreign
        if in_brazilian and in_foreign:
            decision = BrazilianEquityEligibilityDecision(
                company_id=company_id,
                status="CONFLICTING_CVM_REGISTRY_CLASSIFICATION",
                eligible=False,
                evidence_sources=("CVM_CAD", "CVM_FOREIGN_ISSUER_CAD"),
                reason=(
                    "The same canonical CVM identity is present in both Brazilian public-company "
                    "and foreign-issuer registries; eligibility fails closed until the source "
                    "conflict is resolved."
                ),
            )
        elif in_foreign:
            decision = BrazilianEquityEligibilityDecision(
                company_id=company_id,
                status="EXCLUDED_FOREIGN_ISSUER",
                eligible=False,
                evidence_sources=("CVM_FOREIGN_ISSUER_CAD",),
                reason=(
                    "The canonical CVM identity is registered as a foreign issuer. The project "
                    "universe is Brazilian-company equities, so the issuer is outside that "
                    "universe contract."
                ),
            )
        elif in_brazilian:
            decision = BrazilianEquityEligibilityDecision(
                company_id=company_id,
                status="ELIGIBLE_BRAZILIAN_PUBLIC_COMPANY",
                eligible=True,
                evidence_sources=("CVM_CAD",),
                reason=(
                    "The canonical CVM identity is present in the Brazilian public-company "
                    "registry and absent from the foreign-issuer registry."
                ),
            )
        else:
            decision = BrazilianEquityEligibilityDecision(
                company_id=company_id,
                status="UNRESOLVED_CVM_REGISTRY_CLASSIFICATION",
                eligible=False,
                evidence_sources=(),
                reason=(
                    "The canonical CVM identity is absent from both jurisdiction registries; "
                    "eligibility fails closed instead of being inferred from ticker or name."
                ),
            )
        decisions.append(decision)

    counts = Counter(decision.status for decision in decisions)
    return BrazilianEquityEligibilityReport(
        decisions=tuple(decisions),
        status_counts=dict(sorted(counts.items())),
        eligible_company_ids=tuple(
            decision.company_id for decision in decisions if decision.eligible
        ),
        excluded_foreign_company_ids=tuple(
            decision.company_id
            for decision in decisions
            if decision.status == "EXCLUDED_FOREIGN_ISSUER"
        ),
        unresolved_company_ids=tuple(
            decision.company_id
            for decision in decisions
            if decision.status == "UNRESOLVED_CVM_REGISTRY_CLASSIFICATION"
        ),
        conflicting_company_ids=tuple(
            decision.company_id
            for decision in decisions
            if decision.status == "CONFLICTING_CVM_REGISTRY_CLASSIFICATION"
        ),
    )


def _canonical_company_ids(values: Iterable[str]) -> tuple[str, ...]:
    normalized: set[str] = set()
    for value in values:
        company_id = str(value).strip().lower()
        if not company_id:
            continue
        if not company_id.startswith("cvm:"):
            raise ValueError(f"company_id must use cvm:<CD_CVM>: {company_id}")
        code = company_id.split(":", 1)[1]
        if not code.isdigit():
            raise ValueError(f"company_id must use numeric CD_CVM: {company_id}")
        normalized.add(f"cvm:{int(code)}")
    return tuple(sorted(normalized, key=lambda item: int(item.split(":", 1)[1])))
