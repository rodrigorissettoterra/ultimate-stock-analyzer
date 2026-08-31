from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

StructuralReviewStatus = Literal[
    "GENERAL_CORPORATE_MODEL_REVIEW_REQUIRED",
    "UNIVERSE_ELIGIBILITY_REVIEW_REQUIRED",
]
_ALLOWED_STATUSES = frozenset(
    {
        "GENERAL_CORPORATE_MODEL_REVIEW_REQUIRED",
        "UNIVERSE_ELIGIBILITY_REVIEW_REQUIRED",
    }
)
_DIAGNOSTIC_ONLY_EFFECT = "diagnostic_only"


@dataclass(frozen=True, slots=True, order=True)
class StructuralApplicabilityReview:
    company_id: str
    issuer_code: str
    status: StructuralReviewStatus
    reason: str
    evidence_contracts: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class StructuralApplicabilityReviewRegistry:
    version: str
    effect: str
    reviews: tuple[StructuralApplicabilityReview, ...]

    @property
    def by_company_id(self) -> dict[str, StructuralApplicabilityReview]:
        return {review.company_id: review for review in self.reviews}


def load_structural_applicability_reviews(
    path: str | Path,
) -> StructuralApplicabilityReviewRegistry:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    version = str(payload.get("version") or "").strip()
    effect = str(payload.get("effect") or "").strip()
    entries = payload.get("reviews")

    if not version:
        raise ValueError("Structural applicability review registry has no version")
    if effect != _DIAGNOSTIC_ONLY_EFFECT:
        raise ValueError(
            "Structural applicability review registry must remain diagnostic_only"
        )
    if not isinstance(entries, list):
        raise TypeError("Structural applicability review registry has no reviews list")

    reviews: list[StructuralApplicabilityReview] = []
    seen_company_ids: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            raise TypeError("Structural applicability review entry must be an object")

        company_id = str(entry.get("company_id") or "").strip().lower()
        issuer_code = str(entry.get("issuer_code") or "").strip().upper()
        status = str(entry.get("status") or "").strip().upper()
        reason = str(entry.get("reason") or "").strip()
        evidence_contracts = entry.get("evidence_contracts")

        if not company_id.startswith("cvm:"):
            raise ValueError(
                "Structural applicability review company_id must use cvm:<CD_CVM>"
            )
        try:
            int(company_id.split(":", 1)[1])
        except ValueError as exc:
            raise ValueError(
                f"Invalid structural applicability company_id: {company_id}"
            ) from exc
        if company_id in seen_company_ids:
            raise ValueError(
                f"Duplicate structural applicability review: company_id={company_id}"
            )
        if not issuer_code:
            raise ValueError(
                f"Structural applicability review has no issuer_code: company_id={company_id}"
            )
        if status not in _ALLOWED_STATUSES:
            raise ValueError(
                f"Unsupported structural applicability review status: {status}"
            )
        if not reason:
            raise ValueError(
                f"Structural applicability review has no reason: company_id={company_id}"
            )
        if not isinstance(evidence_contracts, list) or not evidence_contracts:
            raise ValueError(
                "Structural applicability review must list evidence_contracts: "
                f"company_id={company_id}"
            )

        contracts = tuple(
            dict.fromkeys(
                str(contract).strip().upper()
                for contract in evidence_contracts
                if str(contract).strip()
            )
        )
        if not contracts:
            raise ValueError(
                "Structural applicability review has no valid evidence_contracts: "
                f"company_id={company_id}"
            )

        reviews.append(
            StructuralApplicabilityReview(
                company_id=company_id,
                issuer_code=issuer_code,
                status=status,  # type: ignore[arg-type]
                reason=reason,
                evidence_contracts=contracts,
            )
        )
        seen_company_ids.add(company_id)

    return StructuralApplicabilityReviewRegistry(
        version=version,
        effect=effect,
        reviews=tuple(sorted(reviews)),
    )
