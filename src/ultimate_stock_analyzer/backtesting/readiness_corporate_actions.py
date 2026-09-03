from __future__ import annotations

from collections.abc import Mapping
from datetime import date

from pydantic import BaseModel

from ultimate_stock_analyzer.backtesting.readiness import (
    PRICE_SERIES_UNADJUSTED_FOR_CORPORATE_ACTIONS,
    HistoricalBacktestReadinessReport,
)

CORPORATE_ACTION_M15_PATH_UNVALIDATED = "CORPORATE_ACTION_M15_PATH_UNVALIDATED"
CORPORATE_ACTION_EVIDENCE_UNIVERSE_INCOMPLETE = (
    "CORPORATE_ACTION_EVIDENCE_UNIVERSE_INCOMPLETE"
)
CORPORATE_ACTION_EVIDENCE_WINDOW_INCOMPLETE = (
    "CORPORATE_ACTION_EVIDENCE_WINDOW_INCOMPLETE"
)
CORPORATE_ACTION_SOURCE_COMPLETENESS_UNPROVEN = (
    "CORPORATE_ACTION_SOURCE_COMPLETENESS_UNPROVEN"
)
CORPORATE_ACTION_STRICT_DATASET_NOT_READY = "CORPORATE_ACTION_STRICT_DATASET_NOT_READY"
CORPORATE_ACTION_RAW_PRICE_CONTRACT_INVALID = "CORPORATE_ACTION_RAW_PRICE_CONTRACT_INVALID"

PRICE_TREATMENT_ADJUSTED_CLOSE = "ADJUSTED_CLOSE"
PRICE_TREATMENT_EVENT_AWARE_M15_STRICT = "EVENT_AWARE_M15_STRICT"
PRICE_TREATMENT_EVENT_AWARE_M15_DIAGNOSTIC_ONLY = "EVENT_AWARE_M15_DIAGNOSTIC_ONLY"
PRICE_TREATMENT_RAW_UNADJUSTED_UNRESOLVED = "RAW_UNADJUSTED_UNRESOLVED"

_EXPECTED_EVENT_INTEGRATION_EFFECT = (
    "historical_event_dataset_to_m15_diagnostic_no_readiness_promotion"
)
_DIAGNOSTIC_EVENT_AWARE_BACKTEST = "DIAGNOSTIC_EVENT_AWARE_BACKTEST"


class CorporateActionReadinessEvidence(BaseModel):
    schema_version: str = "0.1"
    effect: str = "corporate_action_readiness_evidence_no_promotion"
    start_date: date
    end_date: date
    tickers: list[str]
    m15_event_aware_path_validated: bool
    raw_price_series_preserved: bool
    price_adjustment_applied: bool
    historical_source_completeness_proven: bool
    strict_event_aware_backtest_ready: bool
    strict_blockers: list[str]
    readiness_promotion_allowed: bool = False
    integration_report_sha256: str | None = None


class HistoricalBacktestReadinessWithCorporateActions(HistoricalBacktestReadinessReport):
    schema_version: str = "1.2"
    corporate_action_evidence_attached: bool
    corporate_action_evidence_tickers: list[str]
    corporate_action_evidence_start_date: date | None
    corporate_action_evidence_end_date: date | None
    corporate_action_integration_report_sha256: str | None
    corporate_action_evidence_matches_requested_universe: bool
    corporate_action_evidence_covers_requested_window: bool
    corporate_action_m15_event_aware_path_validated: bool
    corporate_action_historical_source_completeness_proven: bool
    corporate_action_strict_event_aware_backtest_ready: bool
    corporate_action_readiness_blockers: list[str]
    price_treatment_mode: str


def corporate_action_readiness_evidence_from_integration_report(
    payload: Mapping[str, object],
    *,
    integration_report_sha256: str | None = None,
) -> CorporateActionReadinessEvidence:
    """Convert bounded M15 integration output into scoped readiness evidence."""
    if payload.get("effect") != _EXPECTED_EVENT_INTEGRATION_EFFECT:
        raise ValueError("unexpected historical event integration effect")

    dataset = _mapping(payload.get("dataset"), "dataset")
    comparison = _mapping(
        payload.get("diagnostic_m15_comparison"),
        "diagnostic_m15_comparison",
    )
    warnings = _string_list(
        comparison.get("event_aware_warnings"),
        "diagnostic_m15_comparison.event_aware_warnings",
    )
    raw_return = _number(
        comparison.get("raw_asset_return"),
        "diagnostic_m15_comparison.raw_asset_return",
    )
    event_aware_return = _number(
        comparison.get("event_aware_asset_return"),
        "diagnostic_m15_comparison.event_aware_asset_return",
    )
    m15_path_validated = (
        comparison.get("diagnostic_only") is True
        and comparison.get("readiness_promotion_allowed") is False
        and _DIAGNOSTIC_EVENT_AWARE_BACKTEST in warnings
        and raw_return != event_aware_return
    )

    return CorporateActionReadinessEvidence(
        start_date=date.fromisoformat(_string(dataset.get("start_date"), "dataset.start_date")),
        end_date=date.fromisoformat(_string(dataset.get("end_date"), "dataset.end_date")),
        tickers=_string_list(dataset.get("tickers"), "dataset.tickers"),
        m15_event_aware_path_validated=m15_path_validated,
        raw_price_series_preserved=_boolean(
            dataset.get("raw_price_series_preserved"),
            "dataset.raw_price_series_preserved",
        ),
        price_adjustment_applied=_boolean(
            dataset.get("price_adjustment_applied"),
            "dataset.price_adjustment_applied",
        ),
        historical_source_completeness_proven=_boolean(
            dataset.get("historical_source_completeness_proven"),
            "dataset.historical_source_completeness_proven",
        ),
        strict_event_aware_backtest_ready=_boolean(
            dataset.get("strict_event_aware_backtest_ready"),
            "dataset.strict_event_aware_backtest_ready",
        ),
        strict_blockers=_string_list(
            dataset.get("strict_blockers"),
            "dataset.strict_blockers",
        ),
        readiness_promotion_allowed=_boolean(
            dataset.get("readiness_promotion_allowed"),
            "dataset.readiness_promotion_allowed",
        ),
        integration_report_sha256=integration_report_sha256,
    )


def integrate_corporate_action_readiness(
    base_report: HistoricalBacktestReadinessReport,
    evidence: CorporateActionReadinessEvidence | None,
) -> HistoricalBacktestReadinessWithCorporateActions:
    """Add event-aware price treatment to the global readiness decision.

    Raw COTAHIST may become strict-backtest ready without synthetic adjusted prices,
    but only when event evidence covers the exact ticker/date scope and has no blocker.
    """
    (
        universe_match,
        window_coverage,
        strict_applicable,
        event_blockers,
        price_treatment_mode,
    ) = _assess_price_treatment(base_report=base_report, evidence=evidence)

    blockers = set(base_report.blockers)
    if base_report.unadjusted_price_bars:
        if strict_applicable:
            blockers.discard(PRICE_SERIES_UNADJUSTED_FOR_CORPORATE_ACTIONS)
        else:
            blockers.add(PRICE_SERIES_UNADJUSTED_FOR_CORPORATE_ACTIONS)
            blockers.update(event_blockers)

    ordered_blockers = sorted(blockers)
    ready = not ordered_blockers
    payload = base_report.model_dump()
    payload.update(
        {
            "schema_version": "1.2",
            "corporate_action_evidence_attached": evidence is not None,
            "corporate_action_evidence_tickers": (
                [] if evidence is None else list(evidence.tickers)
            ),
            "corporate_action_evidence_start_date": (
                None if evidence is None else evidence.start_date
            ),
            "corporate_action_evidence_end_date": (
                None if evidence is None else evidence.end_date
            ),
            "corporate_action_integration_report_sha256": (
                None if evidence is None else evidence.integration_report_sha256
            ),
            "corporate_action_evidence_matches_requested_universe": universe_match,
            "corporate_action_evidence_covers_requested_window": window_coverage,
            "corporate_action_m15_event_aware_path_validated": (
                False if evidence is None else evidence.m15_event_aware_path_validated
            ),
            "corporate_action_historical_source_completeness_proven": (
                False if evidence is None else evidence.historical_source_completeness_proven
            ),
            "corporate_action_strict_event_aware_backtest_ready": strict_applicable,
            "corporate_action_readiness_blockers": sorted(event_blockers),
            "price_treatment_mode": price_treatment_mode,
            "blockers": ordered_blockers,
            "strict_historical_backtest_data_ready": ready,
            "walk_forward_data_ready": ready,
            "point_in_time_eligible": ready,
        }
    )
    return HistoricalBacktestReadinessWithCorporateActions.model_validate(payload)


def _assess_price_treatment(
    *,
    base_report: HistoricalBacktestReadinessReport,
    evidence: CorporateActionReadinessEvidence | None,
) -> tuple[bool, bool, bool, set[str], str]:
    if evidence is None:
        mode = (
            PRICE_TREATMENT_ADJUSTED_CLOSE
            if base_report.unadjusted_price_bars == 0
            else PRICE_TREATMENT_RAW_UNADJUSTED_UNRESOLVED
        )
        return False, False, False, set(), mode
    if evidence.readiness_promotion_allowed:
        raise ValueError("corporate-action evidence cannot promote readiness directly")

    requested = {ticker.upper() for ticker in base_report.requested_tickers}
    evidence_tickers = {ticker.upper() for ticker in evidence.tickers}
    universe_match = bool(requested) and requested.issubset(evidence_tickers)
    window_start = date(base_report.start_year, 1, 1)
    window_end = date(base_report.end_year, 12, 31)
    window_coverage = evidence.start_date <= window_start and evidence.end_date >= window_end

    event_blockers = set(evidence.strict_blockers)
    if not evidence.m15_event_aware_path_validated:
        event_blockers.add(CORPORATE_ACTION_M15_PATH_UNVALIDATED)
    if not evidence.raw_price_series_preserved or evidence.price_adjustment_applied:
        event_blockers.add(CORPORATE_ACTION_RAW_PRICE_CONTRACT_INVALID)
    if not evidence.historical_source_completeness_proven:
        event_blockers.add(CORPORATE_ACTION_SOURCE_COMPLETENESS_UNPROVEN)
    if not evidence.strict_event_aware_backtest_ready:
        event_blockers.add(CORPORATE_ACTION_STRICT_DATASET_NOT_READY)
    if not universe_match:
        event_blockers.add(CORPORATE_ACTION_EVIDENCE_UNIVERSE_INCOMPLETE)
    if not window_coverage:
        event_blockers.add(CORPORATE_ACTION_EVIDENCE_WINDOW_INCOMPLETE)

    strict_applicable = (
        evidence.m15_event_aware_path_validated
        and evidence.raw_price_series_preserved
        and not evidence.price_adjustment_applied
        and evidence.historical_source_completeness_proven
        and evidence.strict_event_aware_backtest_ready
        and universe_match
        and window_coverage
        and not event_blockers
    )
    if base_report.unadjusted_price_bars == 0:
        mode = PRICE_TREATMENT_ADJUSTED_CLOSE
    elif strict_applicable:
        mode = PRICE_TREATMENT_EVENT_AWARE_M15_STRICT
    elif evidence.m15_event_aware_path_validated:
        mode = PRICE_TREATMENT_EVENT_AWARE_M15_DIAGNOSTIC_ONLY
    else:
        mode = PRICE_TREATMENT_RAW_UNADJUSTED_UNRESOLVED

    return universe_match, window_coverage, strict_applicable, event_blockers, mode


def _mapping(value: object, field: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field} must be an object")
    return value


def _string(value: object, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field} must be a non-empty string")
    return value


def _string_list(value: object, field: str) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError(f"{field} must be a list of strings")
    return list(value)


def _boolean(value: object, field: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{field} must be a boolean")
    return value


def _number(value: object, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValueError(f"{field} must be numeric")
    return float(value)
