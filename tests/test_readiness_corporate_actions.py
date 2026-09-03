from __future__ import annotations

from datetime import UTC, date, datetime

from ultimate_stock_analyzer.backtesting.readiness import (
    PRICE_SERIES_UNADJUSTED_FOR_CORPORATE_ACTIONS,
    HistoricalBacktestReadinessReport,
)
from ultimate_stock_analyzer.backtesting.readiness_corporate_actions import (
    CORPORATE_ACTION_EVIDENCE_UNIVERSE_INCOMPLETE,
    CORPORATE_ACTION_M15_PATH_UNVALIDATED,
    CORPORATE_ACTION_PRICE_PROVENANCE_MISMATCH,
    CORPORATE_ACTION_SOURCE_COMPLETENESS_UNPROVEN,
    PRICE_TREATMENT_EVENT_AWARE_M15_DIAGNOSTIC_ONLY,
    PRICE_TREATMENT_EVENT_AWARE_M15_STRICT,
    PRICE_TREATMENT_RAW_UNADJUSTED_UNRESOLVED,
    CorporateActionReadinessEvidence,
    corporate_action_readiness_evidence_from_integration_report,
    integrate_corporate_action_readiness,
)

NOW = datetime(2026, 9, 3, tzinfo=UTC)
PRICE_FINGERPRINT = "b" * 64


def _base_report() -> HistoricalBacktestReadinessReport:
    return HistoricalBacktestReadinessReport(
        generated_at=NOW,
        bootstrap_run_id="readiness-ca-test",
        bootstrap_manifest_sha256="a" * 64,
        start_year=2024,
        end_year=2025,
        requested_tickers=["TEST3"],
        source_policy="OFFICIAL_FREE_FIRST",
        fundamental_companies=1,
        fundamental_company_years=2,
        point_in_time_critical_complete_company_years=2,
        fundamental_point_in_time_gap_count=0,
        fundamental_point_in_time_gap_details_complete=True,
        fundamental_point_in_time_gaps=[],
        longitudinal_pair_ready_company_years=1,
        resolved_sector_model_company_years=2,
        specialized_contract_required_company_years=0,
        sector_classification_records=1,
        point_in_time_sector_classification_records=1,
        bank_profiles=0,
        point_in_time_bank_profiles=0,
        expected_ticker_years=2,
        security_ticker_years=2,
        price_ticker_years=2,
        missing_security_ticker_years=[],
        missing_price_ticker_years=[],
        price_bars=2,
        adjusted_price_bars=0,
        unadjusted_price_bars=2,
        blockers=[PRICE_SERIES_UNADJUSTED_FOR_CORPORATE_ACTIONS],
        strict_historical_backtest_data_ready=False,
        walk_forward_data_ready=False,
        point_in_time_eligible=False,
    )


def _evidence(
    *,
    tickers: list[str] | None = None,
    source_complete: bool,
    strict_ready: bool,
    price_fingerprint: str = PRICE_FINGERPRINT,
    strict_blockers: list[str] | None = None,
) -> CorporateActionReadinessEvidence:
    return CorporateActionReadinessEvidence(
        start_date=date(2024, 1, 1),
        end_date=date(2025, 12, 31),
        tickers=tickers or ["TEST3"],
        raw_price_fingerprint_sha256=price_fingerprint,
        m15_event_aware_path_validated=True,
        raw_price_series_preserved=True,
        price_adjustment_applied=False,
        historical_source_completeness_proven=source_complete,
        strict_event_aware_backtest_ready=strict_ready,
        strict_blockers=strict_blockers or [],
        integration_report_sha256="c" * 64,
    )


def _integration_payload(*, comparison: object) -> dict[str, object]:
    return {
        "effect": "historical_event_dataset_to_m15_diagnostic_no_readiness_promotion",
        "dataset": {
            "start_date": "2024-01-01",
            "end_date": "2025-12-31",
            "tickers": ["MGLU3", "ITSA4"],
            "raw_price_fingerprint_sha256": "e" * 64,
            "raw_price_series_preserved": True,
            "price_adjustment_applied": False,
            "historical_source_completeness_proven": False,
            "strict_event_aware_backtest_ready": False,
            "strict_blockers": ["B3_SUPPLEMENT_HISTORICAL_COMPLETENESS_UNPROVEN"],
            "readiness_promotion_allowed": False,
        },
        "diagnostic_m15_comparison": comparison,
    }


def test_diagnostic_event_evidence_keeps_global_price_blocker() -> None:
    report = integrate_corporate_action_readiness(
        _base_report(),
        _evidence(
            source_complete=False,
            strict_ready=False,
            strict_blockers=["B3_SUPPLEMENT_HISTORICAL_COMPLETENESS_UNPROVEN"],
        ),
        audited_raw_price_fingerprint_sha256=PRICE_FINGERPRINT,
    )

    assert report.price_treatment_mode == PRICE_TREATMENT_EVENT_AWARE_M15_DIAGNOSTIC_ONLY
    assert report.corporate_action_m15_event_aware_path_validated
    assert report.corporate_action_evidence_matches_raw_prices
    assert not report.corporate_action_historical_source_completeness_proven
    assert CORPORATE_ACTION_SOURCE_COMPLETENESS_UNPROVEN in report.blockers
    assert PRICE_SERIES_UNADJUSTED_FOR_CORPORATE_ACTIONS in report.blockers
    assert not report.strict_historical_backtest_data_ready


def test_strict_scope_and_price_matched_evidence_can_resolve_raw_price_blocker() -> None:
    report = integrate_corporate_action_readiness(
        _base_report(),
        _evidence(source_complete=True, strict_ready=True),
        audited_raw_price_fingerprint_sha256=PRICE_FINGERPRINT,
    )

    assert report.price_treatment_mode == PRICE_TREATMENT_EVENT_AWARE_M15_STRICT
    assert report.corporate_action_evidence_matches_requested_universe
    assert report.corporate_action_evidence_covers_requested_window
    assert report.corporate_action_evidence_matches_raw_prices
    assert report.corporate_action_strict_event_aware_backtest_ready
    assert PRICE_SERIES_UNADJUSTED_FOR_CORPORATE_ACTIONS not in report.blockers
    assert report.blockers == []
    assert report.strict_historical_backtest_data_ready
    assert report.walk_forward_data_ready
    assert report.point_in_time_eligible
    assert report.adjusted_price_bars == 0
    assert report.unadjusted_price_bars == 2


def test_scope_mismatch_never_unlocks_unadjusted_prices() -> None:
    report = integrate_corporate_action_readiness(
        _base_report(),
        _evidence(tickers=["OTHER3"], source_complete=True, strict_ready=True),
        audited_raw_price_fingerprint_sha256=PRICE_FINGERPRINT,
    )

    assert not report.corporate_action_evidence_matches_requested_universe
    assert CORPORATE_ACTION_EVIDENCE_UNIVERSE_INCOMPLETE in report.blockers
    assert PRICE_SERIES_UNADJUSTED_FOR_CORPORATE_ACTIONS in report.blockers
    assert not report.strict_historical_backtest_data_ready


def test_price_fingerprint_mismatch_never_unlocks_unadjusted_prices() -> None:
    report = integrate_corporate_action_readiness(
        _base_report(),
        _evidence(
            source_complete=True,
            strict_ready=True,
            price_fingerprint="d" * 64,
        ),
        audited_raw_price_fingerprint_sha256=PRICE_FINGERPRINT,
    )

    assert not report.corporate_action_evidence_matches_raw_prices
    assert CORPORATE_ACTION_PRICE_PROVENANCE_MISMATCH in report.blockers
    assert PRICE_SERIES_UNADJUSTED_FOR_CORPORATE_ACTIONS in report.blockers
    assert not report.strict_historical_backtest_data_ready


def test_parser_marks_live_style_diagnostic_m15_path_as_validated() -> None:
    comparison = {
        "diagnostic_only": True,
        "readiness_promotion_allowed": False,
        "raw_asset_return": 8.310606060606059,
        "event_aware_asset_return": -0.06893939393939397,
        "event_aware_warnings": ["DIAGNOSTIC_EVENT_AWARE_BACKTEST"],
    }
    evidence = corporate_action_readiness_evidence_from_integration_report(
        _integration_payload(comparison=comparison),
        integration_report_sha256="f" * 64,
    )

    assert evidence.m15_event_aware_path_validated
    assert evidence.tickers == ["MGLU3", "ITSA4"]
    assert evidence.raw_price_fingerprint_sha256 == "e" * 64
    assert not evidence.historical_source_completeness_proven
    assert not evidence.strict_event_aware_backtest_ready
    assert not evidence.readiness_promotion_allowed
    assert evidence.integration_report_sha256 == "f" * 64


def test_null_diagnostic_comparison_is_attached_as_unvalidated_path() -> None:
    evidence = corporate_action_readiness_evidence_from_integration_report(
        _integration_payload(comparison=None),
        integration_report_sha256="f" * 64,
    )

    assert not evidence.m15_event_aware_path_validated

    report = integrate_corporate_action_readiness(
        _base_report(),
        evidence,
        audited_raw_price_fingerprint_sha256="e" * 64,
    )
    assert CORPORATE_ACTION_M15_PATH_UNVALIDATED in report.blockers
    assert report.price_treatment_mode == PRICE_TREATMENT_RAW_UNADJUSTED_UNRESOLVED
    assert not report.strict_historical_backtest_data_ready
