from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass

from ultimate_stock_analyzer.domain.master import SectorClassificationRecord
from ultimate_stock_analyzer.fundamentals.itsa_holding_contract import (
    ITSA_COMPANY_ID,
    ITSA_HOLDING_ACCOUNT_BINDINGS,
    ITSA_HOLDING_CVM_CONTRACT,
)
from ultimate_stock_analyzer.scoring.sector_models import (
    SectorModelRegistry,
    SectorModelSelection,
)
from ultimate_stock_analyzer.scoring.statement_tree_audit import (
    FinancialStatementTreeAuditReport,
)

CandidateDisposition = str


@dataclass(frozen=True, slots=True)
class ItsaPeerAnchor:
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
class ItsaPeerSchemaEvidence:
    company_id: str
    reference_date: str | None
    exact_concepts: tuple[str, ...]
    missing_concepts: tuple[str, ...]
    label_mismatch_concepts: tuple[str, ...]
    ambiguous_concepts: tuple[str, ...]
    critical_required_concepts: tuple[str, ...]
    critical_exact_concepts: tuple[str, ...]
    critical_schema_coverage: float
    total_schema_coverage: float
    exact_schema_match: bool
    point_in_time_eligible: bool = False


@dataclass(frozen=True, slots=True)
class ItsaPeerCandidate:
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
    disposition: CandidateDisposition
    schema_evidence: ItsaPeerSchemaEvidence | None
    history_validation_candidate: bool


@dataclass(frozen=True, slots=True)
class ItsaPeerDiscoveryReport:
    anchor: ItsaPeerAnchor
    anchor_schema_evidence: ItsaPeerSchemaEvidence
    min_comparable_peers_for_cross_sectional_score: int
    exact_segment_candidate_count: int
    exact_segment_company_count_including_itsa: int
    exact_segment_numerical_minimum_reachable: bool
    disposition_counts: dict[str, int]
    history_validation_candidate_company_ids: tuple[str, ...]
    history_validation_candidate_count: int
    potential_peer_count_including_itsa: int
    cross_sectional_minimum_reachable_after_schema: bool
    peer_set_ready: bool
    scoring_ready: bool
    routing_ready: bool
    applicability_registry_resolvable: bool
    status: str
    candidates: tuple[ItsaPeerCandidate, ...]
    effect: str = "diagnostic_only_no_scoring_or_routing"
    point_in_time_eligible: bool = False

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def discover_itsa_exact_segment_candidates(
    classifications: list[SectorClassificationRecord],
    *,
    registry: SectorModelRegistry,
) -> tuple[ItsaPeerAnchor, tuple[ItsaPeerCandidate, ...]]:
    """Discover current eligible companies in ITSA's exact B3 segment.

    Current sector-model routing is captured as context only. It never removes an
    exact-segment candidate from the diagnostic, so this audit remains useful if a
    holding-specific route is introduced later.
    """

    anchors = [record for record in classifications if record.company_id == ITSA_COMPANY_ID]
    if len(anchors) != 1:
        raise ValueError(
            "ITSA peer discovery requires exactly one eligible classification anchor: "
            f"company_id={ITSA_COMPANY_ID} matches={len(anchors)}"
        )
    anchor_record = anchors[0]
    anchor_selection = _selection(registry, anchor_record)
    anchor = ItsaPeerAnchor(
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

    candidates: list[ItsaPeerCandidate] = []
    for record in classifications:
        if record.company_id == ITSA_COMPANY_ID:
            continue
        if not _same_exact_segment(anchor_record, record):
            continue
        selection = _selection(registry, record)
        candidates.append(
            ItsaPeerCandidate(
                company_id=record.company_id,
                cvm_code=record.cvm_code,
                issuer_code=record.issuer_code,
                trading_name=record.trading_name,
                sector=record.sector,
                subsector=record.subsector,
                segment=record.segment,
                model_id=selection.model_id,
                selection_reason=selection.reason,
                is_fallback=selection.is_fallback,
                disposition="NO_DFP_EVIDENCE",
                schema_evidence=None,
                history_validation_candidate=False,
            )
        )
    return anchor, tuple(sorted(candidates, key=lambda item: (item.issuer_code, item.company_id)))


def compare_itsa_holding_schema(
    report: FinancialStatementTreeAuditReport,
) -> ItsaPeerSchemaEvidence:
    exact: list[str] = []
    missing: list[str] = []
    mismatched: list[str] = []
    ambiguous: list[str] = []

    for binding in ITSA_HOLDING_ACCOUNT_BINDINGS:
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
    critical_required = tuple(sorted(ITSA_HOLDING_CVM_CONTRACT.critical_inputs))
    critical_exact = tuple(sorted(exact_set & set(critical_required)))
    return ItsaPeerSchemaEvidence(
        company_id=report.company_id,
        reference_date=(
            report.reference_date.isoformat() if report.reference_date is not None else None
        ),
        exact_concepts=tuple(sorted(exact)),
        missing_concepts=tuple(sorted(missing)),
        label_mismatch_concepts=tuple(sorted(mismatched)),
        ambiguous_concepts=tuple(sorted(ambiguous)),
        critical_required_concepts=critical_required,
        critical_exact_concepts=critical_exact,
        critical_schema_coverage=len(critical_exact) / len(critical_required),
        total_schema_coverage=len(exact) / len(ITSA_HOLDING_ACCOUNT_BINDINGS),
        exact_schema_match=(
            len(exact) == len(ITSA_HOLDING_ACCOUNT_BINDINGS)
            and not missing
            and not mismatched
            and not ambiguous
        ),
    )


def evaluate_itsa_peer_discovery(
    *,
    anchor: ItsaPeerAnchor,
    candidates: tuple[ItsaPeerCandidate, ...],
    statement_reports: dict[str, FinancialStatementTreeAuditReport],
    min_comparable_peers_for_cross_sectional_score: int,
) -> ItsaPeerDiscoveryReport:
    if min_comparable_peers_for_cross_sectional_score < 2:
        raise ValueError("ITSA comparable peer minimum must be at least 2")

    anchor_report = statement_reports.get(anchor.company_id)
    if anchor_report is None or not anchor_report.lines:
        raise ValueError("ITSA peer discovery has no anchor DFP evidence")
    anchor_schema = compare_itsa_holding_schema(anchor_report)
    if not anchor_schema.exact_schema_match:
        raise ValueError(
            "ITSA peer discovery anchor no longer exactly matches its accounting contract"
        )

    evaluated: list[ItsaPeerCandidate] = []
    for candidate in candidates:
        report = statement_reports.get(candidate.company_id)
        if report is None or not report.lines:
            evaluated.append(candidate)
            continue
        evidence = compare_itsa_holding_schema(report)
        compatible = evidence.critical_schema_coverage == 1.0
        disposition = (
            "CRITICAL_SCHEMA_COMPATIBLE_REQUIRES_HISTORY_VALIDATION"
            if compatible
            else "SCHEMA_MISMATCH"
        )
        evaluated.append(
            ItsaPeerCandidate(
                company_id=candidate.company_id,
                cvm_code=candidate.cvm_code,
                issuer_code=candidate.issuer_code,
                trading_name=candidate.trading_name,
                sector=candidate.sector,
                subsector=candidate.subsector,
                segment=candidate.segment,
                model_id=candidate.model_id,
                selection_reason=candidate.selection_reason,
                is_fallback=candidate.is_fallback,
                disposition=disposition,
                schema_evidence=evidence,
                history_validation_candidate=compatible,
            )
        )

    evaluated_tuple = tuple(sorted(evaluated, key=lambda item: (item.issuer_code, item.company_id)))
    history_ids = tuple(
        item.company_id for item in evaluated_tuple if item.history_validation_candidate
    )
    exact_segment_count = 1 + len(evaluated_tuple)
    numerical_minimum_reachable = (
        exact_segment_count >= min_comparable_peers_for_cross_sectional_score
    )
    potential_peer_count = 1 + len(history_ids)
    schema_minimum_reachable = (
        potential_peer_count >= min_comparable_peers_for_cross_sectional_score
    )

    if not numerical_minimum_reachable:
        status = "CROSS_SECTIONAL_MINIMUM_UNREACHABLE_IN_CURRENT_EXACT_B3_SEGMENT"
    elif not history_ids:
        status = "NO_CRITICAL_SCHEMA_COMPATIBLE_PEERS_IN_CURRENT_EXACT_B3_SEGMENT"
    elif not schema_minimum_reachable:
        status = "INSUFFICIENT_SCHEMA_COMPATIBLE_PEERS_IN_CURRENT_EXACT_B3_SEGMENT"
    else:
        status = "SCHEMA_CANDIDATE_GATE_PASSED_REQUIRES_HISTORY_VALIDATION"

    disposition_counts = Counter(item.disposition for item in evaluated_tuple)
    return ItsaPeerDiscoveryReport(
        anchor=anchor,
        anchor_schema_evidence=anchor_schema,
        min_comparable_peers_for_cross_sectional_score=(
            min_comparable_peers_for_cross_sectional_score
        ),
        exact_segment_candidate_count=len(evaluated_tuple),
        exact_segment_company_count_including_itsa=exact_segment_count,
        exact_segment_numerical_minimum_reachable=numerical_minimum_reachable,
        disposition_counts=dict(sorted(disposition_counts.items())),
        history_validation_candidate_company_ids=history_ids,
        history_validation_candidate_count=len(history_ids),
        potential_peer_count_including_itsa=potential_peer_count,
        cross_sectional_minimum_reachable_after_schema=schema_minimum_reachable,
        peer_set_ready=False,
        scoring_ready=False,
        routing_ready=False,
        applicability_registry_resolvable=False,
        status=status,
        candidates=evaluated_tuple,
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


def _same_exact_segment(
    anchor: SectorClassificationRecord,
    candidate: SectorClassificationRecord,
) -> bool:
    return (
        _text_key(anchor.sector) == _text_key(candidate.sector)
        and _text_key(anchor.subsector) == _text_key(candidate.subsector)
        and _text_key(anchor.segment) == _text_key(candidate.segment)
    )


def _text_key(value: str) -> str:
    return " ".join(str(value).split()).casefold()


def _normalize_label(value: str) -> str:
    return " ".join(str(value).split())
