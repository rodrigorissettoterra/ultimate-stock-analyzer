from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass
from typing import Literal

from ultimate_stock_analyzer.domain.master import SectorClassificationRecord
from ultimate_stock_analyzer.fundamentals.fige_financial_contract import (
    FIGE_COMPANY_ID,
    FIGE_FINANCIAL_ACCOUNT_BINDINGS,
)
from ultimate_stock_analyzer.scoring.sector_models import (
    SectorModelRegistry,
    SectorModelSelection,
)
from ultimate_stock_analyzer.scoring.statement_tree_audit import (
    FinancialStatementTreeAuditReport,
)

PeerScope = Literal["EXACT_SEGMENT", "SAME_SUBSECTOR", "SAME_SECTOR"]
CandidateDisposition = Literal[
    "CONTEXT_ONLY_BROADER_SCOPE",
    "EXCLUDED_SPECIALIZED_MODEL",
    "NO_DFP_EVIDENCE",
    "SCHEMA_MISMATCH",
    "PRIMARY_SCHEMA_COMPATIBLE_REQUIRES_HISTORY_VALIDATION",
]
PRIMARY_METRIC_REQUIRED_CONCEPTS = frozenset(
    {
        "total_assets",
        "net_income",
        "pretax_income",
        "gross_financial_intermediation_result",
        "other_operating_result",
    }
)


@dataclass(frozen=True, slots=True)
class FigePeerAnchor:
    company_id: str
    cvm_code: int
    issuer_code: str
    trading_name: str
    sector: str
    subsector: str
    segment: str
    model_id: str
    selection_reason: str
    is_fallback: bool


@dataclass(frozen=True, slots=True)
class FigePeerSchemaEvidence:
    company_id: str
    reference_date: str | None
    exact_concepts: tuple[str, ...]
    missing_concepts: tuple[str, ...]
    label_mismatch_concepts: tuple[str, ...]
    ambiguous_concepts: tuple[str, ...]
    primary_required_concepts: tuple[str, ...]
    primary_exact_concepts: tuple[str, ...]
    primary_schema_coverage: float
    total_schema_coverage: float
    exact_schema_match: bool
    point_in_time_eligible: bool = False


@dataclass(frozen=True, slots=True)
class FigePeerCandidate:
    company_id: str
    cvm_code: int
    issuer_code: str
    trading_name: str
    sector: str
    subsector: str
    segment: str
    peer_scope: PeerScope
    model_id: str
    selection_reason: str
    is_fallback: bool
    disposition: CandidateDisposition
    schema_evidence: FigePeerSchemaEvidence | None
    history_validation_candidate: bool


@dataclass(frozen=True, slots=True)
class FigePeerDiscoveryReport:
    anchor: FigePeerAnchor
    anchor_schema_evidence: FigePeerSchemaEvidence
    min_comparable_peers_for_cross_sectional_score: int
    candidate_scope_counts: dict[str, int]
    disposition_counts: dict[str, int]
    history_validation_candidate_company_ids: tuple[str, ...]
    history_validation_candidate_count: int
    potential_peer_count_including_fige: int
    cross_sectional_minimum_reachable_in_current_scope: bool
    peer_set_ready: bool
    scoring_ready: bool
    routing_ready: bool
    applicability_registry_resolvable: bool
    status: str
    candidates: tuple[FigePeerCandidate, ...]
    effect: str = "diagnostic_only_no_scoring_or_routing"
    point_in_time_eligible: bool = False

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def discover_fige_classification_candidates(
    classifications: list[SectorClassificationRecord],
    *,
    registry: SectorModelRegistry,
) -> tuple[FigePeerAnchor, tuple[FigePeerCandidate, ...]]:
    anchors = [record for record in classifications if record.company_id == FIGE_COMPANY_ID]
    if len(anchors) != 1:
        raise ValueError(
            "FIGE peer discovery requires exactly one eligible classification anchor: "
            f"company_id={FIGE_COMPANY_ID} matches={len(anchors)}"
        )
    anchor_record = anchors[0]
    anchor_selection = _selection(registry, anchor_record)
    anchor = FigePeerAnchor(
        company_id=anchor_record.company_id,
        cvm_code=anchor_record.cvm_code,
        issuer_code=anchor_record.issuer_code,
        trading_name=anchor_record.trading_name,
        sector=anchor_record.sector,
        subsector=anchor_record.subsector,
        segment=anchor_record.segment,
        model_id=anchor_selection.model_id,
        selection_reason=anchor_selection.reason,
        is_fallback=anchor_selection.is_fallback,
    )
    if not anchor.is_fallback:
        raise ValueError(
            "FIGE peer discovery anchor is no longer on the fallback model; "
            "review the routing change before continuing this diagnostic"
        )

    candidates: list[FigePeerCandidate] = []
    for record in classifications:
        if record.company_id == FIGE_COMPANY_ID:
            continue
        scope = _peer_scope(anchor_record, record)
        if scope is None:
            continue
        selection = _selection(registry, record)
        if scope == "SAME_SECTOR":
            disposition: CandidateDisposition = "CONTEXT_ONLY_BROADER_SCOPE"
        elif not selection.is_fallback:
            disposition = "EXCLUDED_SPECIALIZED_MODEL"
        else:
            disposition = "NO_DFP_EVIDENCE"
        candidates.append(
            FigePeerCandidate(
                company_id=record.company_id,
                cvm_code=record.cvm_code,
                issuer_code=record.issuer_code,
                trading_name=record.trading_name,
                sector=record.sector,
                subsector=record.subsector,
                segment=record.segment,
                peer_scope=scope,
                model_id=selection.model_id,
                selection_reason=selection.reason,
                is_fallback=selection.is_fallback,
                disposition=disposition,
                schema_evidence=None,
                history_validation_candidate=False,
            )
        )
    return anchor, tuple(sorted(candidates, key=_candidate_sort_key))


def compare_fige_financial_schema(
    report: FinancialStatementTreeAuditReport,
) -> FigePeerSchemaEvidence:
    exact: list[str] = []
    missing: list[str] = []
    mismatched: list[str] = []
    ambiguous: list[str] = []

    for binding in FIGE_FINANCIAL_ACCOUNT_BINDINGS:
        matching = [
            line
            for line in report.lines
            if line.statement == binding.statement
            and line.account_code == binding.account_code
        ]
        if not matching:
            missing.append(binding.concept_id)
            continue
        if len(matching) > 1:
            ambiguous.append(binding.concept_id)
            continue
        line = matching[0]
        if _normalize_label(line.account_name) != _normalize_label(binding.expected_label):
            mismatched.append(binding.concept_id)
            continue
        exact.append(binding.concept_id)

    exact_set = set(exact)
    primary_exact = tuple(sorted(PRIMARY_METRIC_REQUIRED_CONCEPTS & exact_set))
    primary_required = tuple(sorted(PRIMARY_METRIC_REQUIRED_CONCEPTS))
    return FigePeerSchemaEvidence(
        company_id=report.company_id,
        reference_date=(
            report.reference_date.isoformat() if report.reference_date is not None else None
        ),
        exact_concepts=tuple(sorted(exact)),
        missing_concepts=tuple(sorted(missing)),
        label_mismatch_concepts=tuple(sorted(mismatched)),
        ambiguous_concepts=tuple(sorted(ambiguous)),
        primary_required_concepts=primary_required,
        primary_exact_concepts=primary_exact,
        primary_schema_coverage=len(primary_exact) / len(primary_required),
        total_schema_coverage=len(exact) / len(FIGE_FINANCIAL_ACCOUNT_BINDINGS),
        exact_schema_match=(
            len(exact) == len(FIGE_FINANCIAL_ACCOUNT_BINDINGS)
            and not missing
            and not mismatched
            and not ambiguous
        ),
    )


def evaluate_fige_peer_discovery(
    *,
    anchor: FigePeerAnchor,
    candidates: tuple[FigePeerCandidate, ...],
    statement_reports: dict[str, FinancialStatementTreeAuditReport],
    min_comparable_peers_for_cross_sectional_score: int,
) -> FigePeerDiscoveryReport:
    if min_comparable_peers_for_cross_sectional_score < 2:
        raise ValueError("FIGE comparable peer minimum must be at least 2")
    anchor_report = statement_reports.get(anchor.company_id)
    if anchor_report is None or not anchor_report.lines:
        raise ValueError("FIGE peer discovery has no anchor DFP evidence")
    anchor_schema = compare_fige_financial_schema(anchor_report)
    if not anchor_schema.exact_schema_match:
        raise ValueError(
            "FIGE peer discovery anchor no longer exactly matches its accounting bindings"
        )

    evaluated: list[FigePeerCandidate] = []
    for candidate in candidates:
        if candidate.disposition in {
            "CONTEXT_ONLY_BROADER_SCOPE",
            "EXCLUDED_SPECIALIZED_MODEL",
        }:
            evaluated.append(candidate)
            continue
        report = statement_reports.get(candidate.company_id)
        if report is None or not report.lines:
            evaluated.append(candidate)
            continue
        evidence = compare_fige_financial_schema(report)
        compatible = evidence.primary_schema_coverage == 1.0
        disposition: CandidateDisposition = (
            "PRIMARY_SCHEMA_COMPATIBLE_REQUIRES_HISTORY_VALIDATION"
            if compatible
            else "SCHEMA_MISMATCH"
        )
        evaluated.append(
            FigePeerCandidate(
                company_id=candidate.company_id,
                cvm_code=candidate.cvm_code,
                issuer_code=candidate.issuer_code,
                trading_name=candidate.trading_name,
                sector=candidate.sector,
                subsector=candidate.subsector,
                segment=candidate.segment,
                peer_scope=candidate.peer_scope,
                model_id=candidate.model_id,
                selection_reason=candidate.selection_reason,
                is_fallback=candidate.is_fallback,
                disposition=disposition,
                schema_evidence=evidence,
                history_validation_candidate=compatible,
            )
        )

    evaluated_tuple = tuple(sorted(evaluated, key=_candidate_sort_key))
    history_ids = tuple(
        candidate.company_id
        for candidate in evaluated_tuple
        if candidate.history_validation_candidate
    )
    potential_peer_count = 1 + len(history_ids)
    minimum_reachable = (
        potential_peer_count >= min_comparable_peers_for_cross_sectional_score
    )
    if history_ids:
        status = (
            "SCHEMA_CANDIDATE_GATE_PASSED_REQUIRES_HISTORY_VALIDATION"
            if minimum_reachable
            else "INSUFFICIENT_SCHEMA_CANDIDATES_WITHIN_CURRENT_B3_SUBSECTOR"
        )
    else:
        status = "NO_PRIMARY_SCHEMA_COMPATIBLE_PEERS_WITHIN_CURRENT_B3_SUBSECTOR"

    scope_counts = Counter(candidate.peer_scope for candidate in evaluated_tuple)
    disposition_counts = Counter(candidate.disposition for candidate in evaluated_tuple)
    return FigePeerDiscoveryReport(
        anchor=anchor,
        anchor_schema_evidence=anchor_schema,
        min_comparable_peers_for_cross_sectional_score=(
            min_comparable_peers_for_cross_sectional_score
        ),
        candidate_scope_counts=dict(sorted(scope_counts.items())),
        disposition_counts=dict(sorted(disposition_counts.items())),
        history_validation_candidate_company_ids=history_ids,
        history_validation_candidate_count=len(history_ids),
        potential_peer_count_including_fige=potential_peer_count,
        cross_sectional_minimum_reachable_in_current_scope=minimum_reachable,
        peer_set_ready=False,
        scoring_ready=False,
        routing_ready=False,
        applicability_registry_resolvable=False,
        status=status,
        candidates=evaluated_tuple,
    )


def schema_audit_company_ids(
    candidates: tuple[FigePeerCandidate, ...],
) -> tuple[str, ...]:
    return tuple(
        candidate.company_id
        for candidate in candidates
        if candidate.peer_scope in {"EXACT_SEGMENT", "SAME_SUBSECTOR"}
        and candidate.is_fallback
    )


def _selection(
    registry: SectorModelRegistry,
    record: SectorClassificationRecord,
) -> SectorModelSelection:
    return registry.select(
        {
            "sector": record.sector,
            "subsector": record.subsector,
            "segment": record.segment,
            "industry": None,
        }
    )


def _peer_scope(
    anchor: SectorClassificationRecord,
    candidate: SectorClassificationRecord,
) -> PeerScope | None:
    if _text_key(anchor.sector) != _text_key(candidate.sector):
        return None
    if _text_key(anchor.subsector) != _text_key(candidate.subsector):
        return "SAME_SECTOR"
    if _text_key(anchor.segment) != _text_key(candidate.segment):
        return "SAME_SUBSECTOR"
    return "EXACT_SEGMENT"


def _candidate_sort_key(candidate: FigePeerCandidate) -> tuple[int, str, str]:
    scope_order = {
        "EXACT_SEGMENT": 0,
        "SAME_SUBSECTOR": 1,
        "SAME_SECTOR": 2,
    }
    return (
        scope_order[candidate.peer_scope],
        candidate.issuer_code,
        candidate.company_id,
    )


def _text_key(value: str) -> str:
    return " ".join(str(value).split()).casefold()


def _normalize_label(value: str) -> str:
    return " ".join(str(value).split())
