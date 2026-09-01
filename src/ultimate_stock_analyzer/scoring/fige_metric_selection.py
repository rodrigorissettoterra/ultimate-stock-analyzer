from __future__ import annotations

import math
import statistics
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal

import yaml

from ultimate_stock_analyzer.fundamentals.fige_financial_contract import FIGE_COMPANY_ID

MetricSource = Literal["annual_metric", "historical_statistic"]
MetricRole = Literal[
    "PRIMARY_MODEL_CANDIDATE_UNCALIBRATED",
    "SECONDARY_MODEL_CANDIDATE_UNCALIBRATED",
    "GUARDRAIL",
    "DIAGNOSTIC_ONLY",
    "DESCRIPTIVE_ONLY",
]
ConceptRole = Literal["BLOCKED_WITH_CURRENT_CONTRACT"]

_ALLOWED_METRIC_SOURCES = frozenset({"annual_metric", "historical_statistic"})
_ALLOWED_METRIC_ROLES = frozenset(
    {
        "PRIMARY_MODEL_CANDIDATE_UNCALIBRATED",
        "SECONDARY_MODEL_CANDIDATE_UNCALIBRATED",
        "GUARDRAIL",
        "DIAGNOSTIC_ONLY",
        "DESCRIPTIVE_ONLY",
    }
)
_ALLOWED_CONCEPT_ROLES = frozenset({"BLOCKED_WITH_CURRENT_CONTRACT"})
_PROHIBITED_SCORING_KEYS = frozenset(
    {
        "weight",
        "weights",
        "direction",
        "target",
        "tolerance",
        "threshold",
        "thresholds",
        "score",
    }
)
_EXPECTED_EFFECT = "diagnostic_only_no_scoring"


@dataclass(frozen=True, slots=True)
class FigeMetricSelectionRule:
    name: str
    source: MetricSource
    role: MetricRole
    required_observations: int
    rationale: str


@dataclass(frozen=True, slots=True)
class FigeConceptSelectionRule:
    name: str
    role: ConceptRole
    rationale: str


@dataclass(frozen=True, slots=True)
class FigeMetricSelectionContract:
    version: str
    contract_id: str
    company_id: str
    effect: str
    required_years: tuple[int, ...]
    current_exact_company_ids: tuple[str, ...]
    min_comparable_peers_for_cross_sectional_score: int
    metrics: tuple[FigeMetricSelectionRule, ...]
    concepts: tuple[FigeConceptSelectionRule, ...]

    @classmethod
    def from_yaml(cls, path: str | Path) -> FigeMetricSelectionContract:
        raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise TypeError("FIGE metric-selection contract must be a mapping")
        _reject_scoring_configuration(raw)

        company_id = str(raw.get("company_id") or "").strip().lower()
        if company_id != FIGE_COMPANY_ID:
            raise ValueError(
                "FIGE metric-selection contract company identity mismatch: "
                f"expected={FIGE_COMPANY_ID} actual={company_id}"
            )

        effect = str(raw.get("effect") or "").strip()
        if effect != _EXPECTED_EFFECT:
            raise ValueError(
                "FIGE metric-selection contract must remain diagnostic_only_no_scoring"
            )

        required_years = tuple(int(year) for year in raw.get("required_years", ()))
        if not required_years or required_years != tuple(
            range(required_years[0], required_years[-1] + 1)
        ):
            raise ValueError("FIGE metric-selection required_years must be contiguous")

        peer_policy = raw.get("peer_policy")
        if not isinstance(peer_policy, dict):
            raise TypeError("FIGE metric-selection contract has no peer_policy")
        current_exact_company_ids = tuple(
            str(company).strip().lower()
            for company in peer_policy.get("current_exact_company_ids", ())
            if str(company).strip()
        )
        if current_exact_company_ids != (FIGE_COMPANY_ID,):
            raise ValueError(
                "FIGE metric-selection current peer evidence must contain exact FIGE only"
            )
        min_peers = int(
            peer_policy.get("min_comparable_peers_for_cross_sectional_score", 0)
        )
        if min_peers < 2:
            raise ValueError("FIGE cross-sectional peer minimum must be at least 2")

        metrics_raw = raw.get("metrics")
        if not isinstance(metrics_raw, list) or not metrics_raw:
            raise ValueError("FIGE metric-selection contract has no metrics")
        metrics = tuple(_metric_rule(item) for item in metrics_raw)
        metric_names = [rule.name for rule in metrics]
        if len(metric_names) != len(set(metric_names)):
            raise ValueError("FIGE metric-selection metric names must be unique")

        concepts_raw = raw.get("concepts")
        if not isinstance(concepts_raw, list) or not concepts_raw:
            raise ValueError("FIGE metric-selection contract has no blocked concepts")
        concepts = tuple(_concept_rule(item) for item in concepts_raw)
        concept_names = [rule.name for rule in concepts]
        if len(concept_names) != len(set(concept_names)):
            raise ValueError("FIGE metric-selection concept names must be unique")

        return cls(
            version=str(raw.get("version") or "").strip(),
            contract_id=str(raw.get("contract_id") or "").strip(),
            company_id=company_id,
            effect=effect,
            required_years=required_years,
            current_exact_company_ids=current_exact_company_ids,
            min_comparable_peers_for_cross_sectional_score=min_peers,
            metrics=metrics,
            concepts=concepts,
        )


@dataclass(frozen=True, slots=True)
class FigeMetricEvidence:
    name: str
    source: str
    role: str
    required_observations: int
    available_observations: int
    unique_value_count: int
    minimum: float | None
    maximum: float | None
    mean: float | None
    population_stdev: float | None
    empirically_saturated: bool
    rationale: str


@dataclass(frozen=True, slots=True)
class FigeMetricSelectionReport:
    contract_id: str
    contract_version: str
    company_id: str
    start_year: int
    end_year: int
    effect: str
    current_comparable_peer_count: int
    min_comparable_peers_for_cross_sectional_score: int
    scoring_status: str
    score_ready: bool
    routing_ready: bool
    registry_resolvable: bool
    metrics: tuple[FigeMetricEvidence, ...]
    blocked_concepts: tuple[FigeConceptSelectionRule, ...]
    warnings: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def evaluate_fige_metric_selection(
    audit_payload: dict[str, Any],
    contract: FigeMetricSelectionContract,
) -> FigeMetricSelectionReport:
    company_id = str(audit_payload.get("company_id") or "").strip().lower()
    if company_id != contract.company_id:
        raise ValueError(
            "FIGE metric-selection audit identity mismatch: "
            f"expected={contract.company_id} actual={company_id}"
        )
    if audit_payload.get("effect") != "diagnostic_only_not_routed_or_scored":
        raise ValueError("FIGE metric-selection requires diagnostic-only economic audit")
    if audit_payload.get("point_in_time_eligible") is not False:
        raise ValueError("FIGE metric-selection audit must not claim PIT eligibility")

    economic_audit = audit_payload.get("economic_audit")
    if not isinstance(economic_audit, dict):
        raise TypeError("FIGE metric-selection audit has no economic_audit object")
    annual_audits = economic_audit.get("annual_audits")
    if not isinstance(annual_audits, list):
        raise TypeError("FIGE metric-selection audit has no annual_audits list")

    years = tuple(int(item["fiscal_year"]) for item in annual_audits)
    if years != contract.required_years:
        raise ValueError(
            "FIGE metric-selection audit years mismatch: "
            f"expected={contract.required_years} actual={years}"
        )

    historical_statistics = economic_audit.get("historical_statistics")
    if not isinstance(historical_statistics, dict):
        raise TypeError("FIGE metric-selection audit has no historical_statistics")

    evidence: list[FigeMetricEvidence] = []
    for rule in contract.metrics:
        if rule.source == "annual_metric":
            values = [
                _numeric_or_none(item.get("metrics", {}).get(rule.name))
                for item in annual_audits
            ]
        else:
            values = [_numeric_or_none(historical_statistics.get(rule.name))]

        known = [value for value in values if value is not None]
        if len(known) < rule.required_observations:
            raise ValueError(
                "FIGE metric-selection insufficient evidence: "
                f"metric={rule.name} required={rule.required_observations} "
                f"available={len(known)}"
            )
        unique_values = set(known)
        evidence.append(
            FigeMetricEvidence(
                name=rule.name,
                source=rule.source,
                role=rule.role,
                required_observations=rule.required_observations,
                available_observations=len(known),
                unique_value_count=len(unique_values),
                minimum=min(known) if known else None,
                maximum=max(known) if known else None,
                mean=statistics.fmean(known) if known else None,
                population_stdev=statistics.pstdev(known) if known else None,
                empirically_saturated=len(unique_values) <= 1,
                rationale=rule.rationale,
            )
        )

    peer_count = len(contract.current_exact_company_ids)
    if peer_count < contract.min_comparable_peers_for_cross_sectional_score:
        scoring_status = "BLOCKED_INSUFFICIENT_COMPARABLE_PEERS"
    else:
        scoring_status = "PEER_COUNT_GATE_PASSED_REQUIRES_CALIBRATION"

    warnings = [
        "NO_SCORING_WEIGHTS_THRESHOLDS_OR_DIRECTIONS_IN_THIS_CONTRACT",
        "NO_ROUTING_OR_APPLICABILITY_REGISTRY_CHANGE_IN_THIS_BLOCK",
        "LATEST_CVM_ANNUAL_ARCHIVES_ARE_NOT_STRICT_REVISION_HISTORY_PIT_EVIDENCE",
    ]
    saturated = tuple(item.name for item in evidence if item.empirically_saturated)
    if saturated:
        warnings.append("EMPIRICALLY_SATURATED_METRICS:" + ",".join(sorted(saturated)))

    score_ready = False
    routing_ready = False
    registry_resolvable = False
    return FigeMetricSelectionReport(
        contract_id=contract.contract_id,
        contract_version=contract.version,
        company_id=contract.company_id,
        start_year=contract.required_years[0],
        end_year=contract.required_years[-1],
        effect=contract.effect,
        current_comparable_peer_count=peer_count,
        min_comparable_peers_for_cross_sectional_score=(
            contract.min_comparable_peers_for_cross_sectional_score
        ),
        scoring_status=scoring_status,
        score_ready=score_ready,
        routing_ready=routing_ready,
        registry_resolvable=registry_resolvable,
        metrics=tuple(evidence),
        blocked_concepts=contract.concepts,
        warnings=tuple(warnings),
    )


def _metric_rule(raw: object) -> FigeMetricSelectionRule:
    if not isinstance(raw, dict):
        raise TypeError("FIGE metric-selection metric rule must be a mapping")
    source = str(raw.get("source") or "").strip()
    role = str(raw.get("role") or "").strip()
    if source not in _ALLOWED_METRIC_SOURCES:
        raise ValueError(f"Unsupported FIGE metric-selection source: {source}")
    if role not in _ALLOWED_METRIC_ROLES:
        raise ValueError(f"Unsupported FIGE metric-selection role: {role}")
    required = int(raw.get("required_observations", 0))
    rationale = str(raw.get("rationale") or "").strip()
    name = str(raw.get("name") or "").strip()
    if not name or not rationale or required < 1:
        raise ValueError("FIGE metric-selection metric rule is incomplete")
    return FigeMetricSelectionRule(
        name=name,
        source=source,  # type: ignore[arg-type]
        role=role,  # type: ignore[arg-type]
        required_observations=required,
        rationale=rationale,
    )


def _concept_rule(raw: object) -> FigeConceptSelectionRule:
    if not isinstance(raw, dict):
        raise TypeError("FIGE metric-selection concept rule must be a mapping")
    role = str(raw.get("role") or "").strip()
    if role not in _ALLOWED_CONCEPT_ROLES:
        raise ValueError(f"Unsupported FIGE metric-selection concept role: {role}")
    name = str(raw.get("name") or "").strip()
    rationale = str(raw.get("rationale") or "").strip()
    if not name or not rationale:
        raise ValueError("FIGE metric-selection concept rule is incomplete")
    return FigeConceptSelectionRule(
        name=name,
        role=role,  # type: ignore[arg-type]
        rationale=rationale,
    )


def _reject_scoring_configuration(value: object, *, path: str = "root") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            normalized_key = str(key).strip().casefold()
            if normalized_key in _PROHIBITED_SCORING_KEYS:
                raise ValueError(
                    "FIGE metric-selection contract cannot contain scoring configuration: "
                    f"{path}.{key}"
                )
            _reject_scoring_configuration(child, path=f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _reject_scoring_configuration(child, path=f"{path}[{index}]")


def _numeric_or_none(value: object) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    return numeric if math.isfinite(numeric) else None
