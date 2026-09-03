from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal

from ultimate_stock_analyzer.backtesting.bcb_ifdata_pit_source_audit import (
    IFDATA_REVISION_HISTORY_UNAVAILABLE,
    IFDATA_ROW_PUBLICATION_TIMESTAMP_UNAVAILABLE,
)
from ultimate_stock_analyzer.backtesting.cvm_bank_net_income_canonical_mapping_audit import (
    CVM_BANK_DFP_PRUDENTIAL_SCOPE_ALIGNMENT_UNPROVEN,
    CVM_BANK_DFP_REVISION_HISTORY_COMPLETENESS_UNPROVEN,
    audit_cvm_bank_net_income_canonical_mapping,
)
from ultimate_stock_analyzer.backtesting.cvm_ipe_pillar3_numeric_values import (
    PILLAR3_IPE_REVISION_HISTORY_COMPLETENESS_UNPROVEN,
    Pillar3PrudentialObservation,
    audit_pillar3_numeric_values,
)
from ultimate_stock_analyzer.collectors.bcb_ifdata import bank_contract_values
from ultimate_stock_analyzer.domain.master import (
    BankPrudentialAnnualRecord,
    FinancialStatementLine,
)
from ultimate_stock_analyzer.fundamentals.contracts import BANK_PRUDENTIAL_CONTRACT

BANK_EVIDENCE_NOT_POINT_IN_TIME = "BANK_EVIDENCE_NOT_POINT_IN_TIME"
BANK_FIELD_EVIDENCE_MISSING = "BANK_FIELD_EVIDENCE_MISSING"
BANK_FIELD_AVAILABILITY_MISSING = "BANK_FIELD_AVAILABILITY_MISSING"
BANK_FIELD_NOT_YET_AVAILABLE_AS_OF = "BANK_FIELD_NOT_YET_AVAILABLE_AS_OF"

BankFieldEvidenceStatus = Literal[
    "POINT_IN_TIME_ADMISSIBLE",
    "PRESENT_NOT_POINT_IN_TIME",
    "OFFICIAL_SCOPE_MISMATCH",
    "MISSING",
]

_PILLAR3_FIELDS = frozenset(
    {
        "core_equity_tier1_ratio",
        "tier1_ratio",
        "basel_ratio",
        "leverage_ratio",
    }
)


@dataclass(frozen=True, slots=True)
class BankFieldEvidenceObservation:
    source: str
    source_scope: str
    value: float
    available_from: datetime | None
    contract_scope_compatible: bool
    point_in_time_eligible: bool
    blockers: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "source_scope": self.source_scope,
            "value": self.value,
            "available_from": (
                self.available_from.isoformat()
                if self.available_from is not None
                else None
            ),
            "contract_scope_compatible": self.contract_scope_compatible,
            "point_in_time_eligible": self.point_in_time_eligible,
            "blockers": list(self.blockers),
        }


@dataclass(frozen=True, slots=True)
class BankFieldEvidenceDecision:
    field_name: str
    status: BankFieldEvidenceStatus
    selected: BankFieldEvidenceObservation | None
    alternatives: tuple[BankFieldEvidenceObservation, ...]
    contract_admissible: bool
    blockers: tuple[str, ...]

    @property
    def value(self) -> float | None:
        return None if self.selected is None else self.selected.value

    @property
    def source(self) -> str | None:
        return None if self.selected is None else self.selected.source

    @property
    def source_scope(self) -> str | None:
        return None if self.selected is None else self.selected.source_scope

    @property
    def available_from(self) -> datetime | None:
        return None if self.selected is None else self.selected.available_from

    @property
    def point_in_time_eligible(self) -> bool:
        return (
            self.selected is not None
            and self.selected.point_in_time_eligible
            and self.contract_admissible
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "field_name": self.field_name,
            "status": self.status,
            "value": self.value,
            "source": self.source,
            "source_scope": self.source_scope,
            "available_from": (
                self.available_from.isoformat()
                if self.available_from is not None
                else None
            ),
            "contract_admissible": self.contract_admissible,
            "point_in_time_eligible": self.point_in_time_eligible,
            "blockers": list(self.blockers),
            "alternatives": [item.to_dict() for item in self.alternatives],
        }


@dataclass(frozen=True, slots=True)
class BankFieldEvidenceRoutingReport:
    company_id: str
    fiscal_year: int
    as_of: datetime
    decisions: tuple[BankFieldEvidenceDecision, ...]
    observed_critical_coverage: float
    contract_scope_compatible_critical_coverage: float
    strict_point_in_time_critical_coverage: float
    bank_evidence_point_in_time_ready: bool
    blockers: tuple[str, ...]
    readiness_promotion_allowed: bool = False
    schema_version: str = "0.1"

    @property
    def effect(self) -> str:
        return "diagnostic_bank_field_evidence_routing_no_readiness_promotion"

    def decision_for(self, field_name: str) -> BankFieldEvidenceDecision:
        for decision in self.decisions:
            if decision.field_name == field_name:
                return decision
        raise KeyError(field_name)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "effect": self.effect,
            "company_id": self.company_id,
            "fiscal_year": self.fiscal_year,
            "as_of": self.as_of.isoformat(),
            "contract": BANK_PRUDENTIAL_CONTRACT.name,
            "decisions": [item.to_dict() for item in self.decisions],
            "observed_critical_coverage": self.observed_critical_coverage,
            "contract_scope_compatible_critical_coverage": (
                self.contract_scope_compatible_critical_coverage
            ),
            "strict_point_in_time_critical_coverage": (
                self.strict_point_in_time_critical_coverage
            ),
            "bank_evidence_point_in_time_ready": (
                self.bank_evidence_point_in_time_ready
            ),
            "readiness_promotion_allowed": self.readiness_promotion_allowed,
            "blockers": list(self.blockers),
        }


def route_bank_field_evidence(
    profile: BankPrudentialAnnualRecord,
    *,
    as_of: datetime,
    cvm_lines: Iterable[FinancialStatementLine] = (),
    pillar3_observations: Iterable[Pillar3PrudentialObservation] = (),
) -> BankFieldEvidenceRoutingReport:
    """Route each bank contract field to the strongest evidence available as-of.

    The router is diagnostic and deliberately fail-closed. A source can be official
    and timestamped yet remain inadmissible for the prudential contract because its
    revision lineage is incomplete or its consolidation perimeter differs.
    """

    as_of = _aware(as_of)
    values = bank_contract_values(profile)
    cvm_rows = tuple(cvm_lines)
    pillar3_rows = tuple(pillar3_observations)

    cvm_observations, cvm_blockers = _cvm_net_income_observations(
        profile,
        rows=cvm_rows,
        as_of=as_of,
    )
    pillar3_by_field, pillar3_blockers = _pillar3_observations(
        profile,
        rows=pillar3_rows,
        as_of=as_of,
    )

    fields = (
        BANK_PRUDENTIAL_CONTRACT.critical_inputs
        + BANK_PRUDENTIAL_CONTRACT.supporting_inputs
    )
    decisions = tuple(
        _route_field(
            profile,
            field_name=field_name,
            value=values.get(field_name),
            as_of=as_of,
            cvm_net_income_observations=cvm_observations,
            cvm_blockers=cvm_blockers,
            pillar3_observation=pillar3_by_field.get(field_name),
            pillar3_blockers=pillar3_blockers,
        )
        for field_name in fields
    )

    critical = tuple(
        decision
        for decision in decisions
        if decision.field_name in BANK_PRUDENTIAL_CONTRACT.critical_inputs
    )
    observed = sum(decision.selected is not None for decision in critical)
    scope_compatible = sum(
        decision.selected is not None
        and decision.selected.contract_scope_compatible
        for decision in critical
    )
    strict = sum(decision.point_in_time_eligible for decision in critical)
    denominator = len(critical)
    observed_coverage = observed / denominator if denominator else 1.0
    scope_coverage = scope_compatible / denominator if denominator else 1.0
    strict_coverage = strict / denominator if denominator else 1.0
    ready = strict_coverage == 1.0

    blockers = {
        blocker
        for decision in decisions
        for blocker in decision.blockers
    }
    if not ready:
        blockers.add(BANK_EVIDENCE_NOT_POINT_IN_TIME)

    return BankFieldEvidenceRoutingReport(
        company_id=profile.company_id,
        fiscal_year=profile.fiscal_year,
        as_of=as_of,
        decisions=decisions,
        observed_critical_coverage=observed_coverage,
        contract_scope_compatible_critical_coverage=scope_coverage,
        strict_point_in_time_critical_coverage=strict_coverage,
        bank_evidence_point_in_time_ready=ready,
        blockers=tuple(sorted(blockers)),
    )


def _route_field(
    profile: BankPrudentialAnnualRecord,
    *,
    field_name: str,
    value: float | None,
    as_of: datetime,
    cvm_net_income_observations: tuple[BankFieldEvidenceObservation, ...],
    cvm_blockers: tuple[str, ...],
    pillar3_observation: BankFieldEvidenceObservation | None,
    pillar3_blockers: tuple[str, ...],
) -> BankFieldEvidenceDecision:
    profile_observation, profile_temporal_blocker = _profile_observation(
        profile,
        value=value,
        as_of=as_of,
    )

    if (
        profile_observation is not None
        and profile_observation.point_in_time_eligible
    ):
        alternatives = _alternatives(
            field_name,
            cvm_net_income_observations=cvm_net_income_observations,
            pillar3_observation=pillar3_observation,
            exclude_source=profile_observation.source,
        )
        return BankFieldEvidenceDecision(
            field_name=field_name,
            status="POINT_IN_TIME_ADMISSIBLE",
            selected=profile_observation,
            alternatives=alternatives,
            contract_admissible=True,
            blockers=(),
        )

    if field_name in _PILLAR3_FIELDS and pillar3_observation is not None:
        alternatives = tuple(
            item
            for item in (profile_observation,)
            if item is not None
        )
        blockers = tuple(
            sorted(
                {
                    BANK_EVIDENCE_NOT_POINT_IN_TIME,
                    PILLAR3_IPE_REVISION_HISTORY_COMPLETENESS_UNPROVEN,
                    *pillar3_blockers,
                }
            )
        )
        return BankFieldEvidenceDecision(
            field_name=field_name,
            status="PRESENT_NOT_POINT_IN_TIME",
            selected=pillar3_observation,
            alternatives=alternatives,
            contract_admissible=False,
            blockers=blockers,
        )

    if profile_observation is not None:
        alternatives = _alternatives(
            field_name,
            cvm_net_income_observations=cvm_net_income_observations,
            pillar3_observation=pillar3_observation,
            exclude_source=profile_observation.source,
        )
        blockers = tuple(
            sorted(
                {
                    BANK_EVIDENCE_NOT_POINT_IN_TIME,
                    IFDATA_REVISION_HISTORY_UNAVAILABLE,
                    IFDATA_ROW_PUBLICATION_TIMESTAMP_UNAVAILABLE,
                    *profile_observation.blockers,
                }
            )
        )
        return BankFieldEvidenceDecision(
            field_name=field_name,
            status="PRESENT_NOT_POINT_IN_TIME",
            selected=profile_observation,
            alternatives=alternatives,
            contract_admissible=False,
            blockers=blockers,
        )

    if field_name == "annual_net_income" and cvm_net_income_observations:
        selected = cvm_net_income_observations[-1]
        alternatives = cvm_net_income_observations[:-1]
        blockers = tuple(
            sorted(
                {
                    CVM_BANK_DFP_PRUDENTIAL_SCOPE_ALIGNMENT_UNPROVEN,
                    CVM_BANK_DFP_REVISION_HISTORY_COMPLETENESS_UNPROVEN,
                    *cvm_blockers,
                    *selected.blockers,
                }
            )
        )
        return BankFieldEvidenceDecision(
            field_name=field_name,
            status="OFFICIAL_SCOPE_MISMATCH",
            selected=selected,
            alternatives=alternatives,
            contract_admissible=False,
            blockers=blockers,
        )

    blockers = {BANK_FIELD_EVIDENCE_MISSING}
    if profile_temporal_blocker is not None:
        blockers.add(profile_temporal_blocker)
    if field_name == "annual_net_income" and cvm_blockers:
        blockers.update(cvm_blockers)
    if field_name in _PILLAR3_FIELDS and pillar3_blockers:
        blockers.update(pillar3_blockers)
    return BankFieldEvidenceDecision(
        field_name=field_name,
        status="MISSING",
        selected=None,
        alternatives=(),
        contract_admissible=False,
        blockers=tuple(sorted(blockers)),
    )


def _profile_observation(
    profile: BankPrudentialAnnualRecord,
    *,
    value: float | None,
    as_of: datetime,
) -> tuple[BankFieldEvidenceObservation | None, str | None]:
    if value is None:
        return None, None
    available_from = profile.available_from_estimate
    if available_from is not None:
        available_from = _aware(available_from)
        if available_from > as_of:
            return None, BANK_FIELD_NOT_YET_AVAILABLE_AS_OF

    point_in_time_eligible = bool(
        profile.point_in_time_eligible and available_from is not None
    )
    blockers: set[str] = set()
    if available_from is None:
        blockers.add(BANK_FIELD_AVAILABILITY_MISSING)
    if not profile.point_in_time_eligible:
        blockers.add(BANK_EVIDENCE_NOT_POINT_IN_TIME)

    return (
        BankFieldEvidenceObservation(
            source=profile.source,
            source_scope=profile.source_scope,
            value=float(value),
            available_from=available_from,
            contract_scope_compatible=True,
            point_in_time_eligible=point_in_time_eligible,
            blockers=tuple(sorted(blockers)),
        ),
        None,
    )


def _cvm_net_income_observations(
    profile: BankPrudentialAnnualRecord,
    *,
    rows: tuple[FinancialStatementLine, ...],
    as_of: datetime,
) -> tuple[
    tuple[BankFieldEvidenceObservation, ...],
    tuple[str, ...],
]:
    if not rows:
        return (), ()
    audit = audit_cvm_bank_net_income_canonical_mapping(
        list(rows),
        cvm_code=profile.cvm_code,
        years=(profile.fiscal_year,),
    )
    observations = []
    for validation in audit.versions:
        account = validation.account_309
        if (
            not validation.observed_mapping_validated
            or account is None
            or account.available_from is None
        ):
            continue
        available_from = _aware(account.available_from)
        if available_from > as_of:
            continue
        observations.append(
            BankFieldEvidenceObservation(
                source="CVM_DFP",
                source_scope="ISSUER_CONSOLIDATED",
                value=float(account.value_brl),
                available_from=available_from,
                contract_scope_compatible=False,
                point_in_time_eligible=False,
                blockers=tuple(sorted(audit.blockers)),
            )
        )
    return (
        tuple(
            sorted(
                observations,
                key=lambda item: (
                    item.available_from or datetime.min.replace(tzinfo=UTC),
                    item.value,
                ),
            )
        ),
        tuple(sorted(audit.blockers)),
    )


def _pillar3_observations(
    profile: BankPrudentialAnnualRecord,
    *,
    rows: tuple[Pillar3PrudentialObservation, ...],
    as_of: datetime,
) -> tuple[
    dict[str, BankFieldEvidenceObservation],
    tuple[str, ...],
]:
    relevant = tuple(
        row
        for row in rows
        if row.prudential_reference_date == profile.reference_date
        and _aware(row.available_from) <= as_of
    )
    if not relevant:
        return {}, ()

    audit = audit_pillar3_numeric_values(relevant)
    timeline = audit.timeline_for(profile.reference_date)
    if timeline is None:
        return {}, tuple(sorted(audit.blockers))
    latest = timeline.value_as_of(as_of)
    if latest is None or not audit.numeric_extraction_contract_ready:
        return {}, tuple(sorted(audit.blockers))

    observations = {
        field_name: BankFieldEvidenceObservation(
            source="CVM_IPE_PILLAR3",
            source_scope="PRUDENTIAL_CONGLOMERATE",
            value=float(getattr(latest, field_name)),
            available_from=_aware(latest.available_from),
            contract_scope_compatible=True,
            point_in_time_eligible=False,
            blockers=tuple(sorted(audit.blockers)),
        )
        for field_name in _PILLAR3_FIELDS
    }
    return observations, tuple(sorted(audit.blockers))


def _alternatives(
    field_name: str,
    *,
    cvm_net_income_observations: tuple[BankFieldEvidenceObservation, ...],
    pillar3_observation: BankFieldEvidenceObservation | None,
    exclude_source: str,
) -> tuple[BankFieldEvidenceObservation, ...]:
    alternatives = []
    if field_name == "annual_net_income":
        alternatives.extend(cvm_net_income_observations)
    if field_name in _PILLAR3_FIELDS and pillar3_observation is not None:
        alternatives.append(pillar3_observation)
    return tuple(item for item in alternatives if item.source != exclude_source)


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("bank field evidence timestamps must be timezone-aware")
    return value.astimezone(UTC)
