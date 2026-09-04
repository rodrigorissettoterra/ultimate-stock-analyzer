from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, date, datetime
from pathlib import Path

from ultimate_stock_analyzer.backtesting.raw_price_provenance import (
    bootstrap_raw_price_fingerprint,
)
from ultimate_stock_analyzer.backtesting.readiness import (
    BANK_EVIDENCE_NOT_POINT_IN_TIME,
    FUNDAMENTAL_POINT_IN_TIME_COVERAGE_INCOMPLETE,
    PRICE_SERIES_UNADJUSTED_FOR_CORPORATE_ACTIONS,
    SECTOR_ROUTING_NOT_POINT_IN_TIME,
    SPECIALIZED_EVIDENCE_NOT_POINT_IN_TIME,
    audit_historical_backtest_readiness,
)
from ultimate_stock_analyzer.backtesting.readiness_corporate_actions import (
    CORPORATE_ACTION_EVIDENCE_UNIVERSE_INCOMPLETE,
    CORPORATE_ACTION_PRICE_PROVENANCE_MISMATCH,
    PRICE_TREATMENT_EVENT_AWARE_M15_DIAGNOSTIC_ONLY,
    corporate_action_readiness_evidence_from_integration_report,
    integrate_corporate_action_readiness,
)
from ultimate_stock_analyzer.bootstrap.coverage import FundamentalCoverageProfiler
from ultimate_stock_analyzer.bootstrap.dataset import BootstrapDataset
from ultimate_stock_analyzer.bootstrap.historical_model_routes import (
    persist_historical_model_routes,
)
from ultimate_stock_analyzer.bootstrap.public_data import (
    PublicDataBootstrapPlan,
    PublicDataBootstrapService,
)
from ultimate_stock_analyzer.scoring.sector_models import SectorModelRegistry


DEFAULT_REGISTRY = "config/scoring/sector_registry_v0.6.yml"
DEFAULT_FCA_ROUTE_MAPPING = "config/backtesting/fca_model_routes_v0.2.yml"
EXPECTED_SOURCE_BLOCKERS = {
    BANK_EVIDENCE_NOT_POINT_IN_TIME,
    PRICE_SERIES_UNADJUSTED_FOR_CORPORATE_ACTIONS,
}


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Audit whether an official-source bootstrap run is point-in-time ready "
            "for strict M15/M16 historical evaluation."
        )
    )
    parser.add_argument("--start-year", type=int, required=True)
    parser.add_argument("--end-year", type=int, required=True)
    parser.add_argument("--ticker", action="append", default=[])
    parser.add_argument("--data-dir", required=True)
    parser.add_argument("--registry", default=DEFAULT_REGISTRY)
    parser.add_argument(
        "--fca-route-mapping",
        default=DEFAULT_FCA_ROUTE_MAPPING,
    )
    parser.add_argument(
        "--event-aware-integration-report",
        help=(
            "Optional bounded historical-event/M15 integration JSON. It can prove "
            "the return path but never expands its ticker/date/price provenance scope."
        ),
    )
    parser.add_argument(
        "--output",
        default="historical-backtest-readiness.json",
    )
    args = parser.parse_args()

    collected_at = datetime.now(UTC)
    tickers = tuple(args.ticker)
    if not tickers:
        raise ValueError("readiness audit requires at least one bounded ticker")

    corporate_action_evidence = None
    if args.event_aware_integration_report:
        evidence_path = Path(args.event_aware_integration_report)
        evidence_bytes = evidence_path.read_bytes()
        evidence_payload = json.loads(evidence_bytes)
        if not isinstance(evidence_payload, dict):
            raise TypeError("event-aware integration report must contain one JSON object")
        corporate_action_evidence = corporate_action_readiness_evidence_from_integration_report(
            evidence_payload,
            integration_report_sha256=hashlib.sha256(evidence_bytes).hexdigest(),
        )

    plan = PublicDataBootstrapPlan(
        start_year=args.start_year,
        end_year=args.end_year,
        tickers=tickers,
        include_current_sector_classification=False,
        include_bank_ifdata=True,
    )
    data_dir = Path(args.data_dir)
    manifest = PublicDataBootstrapService(data_dir).run(
        plan,
        collected_at=collected_at,
    )
    run_dir = data_dir / "bootstrap" / manifest.run_id
    persist_historical_model_routes(
        run_dir,
        mapping_path=args.fca_route_mapping,
        sector_registry_path=args.registry,
    )
    dataset = BootstrapDataset(run_dir)
    audited_raw_price_fingerprint = bootstrap_raw_price_fingerprint(
        dataset,
        start_date=date(args.start_year, 1, 1),
        end_date=date(args.end_year, 12, 31),
        tickers=tickers,
    )
    registry = SectorModelRegistry.from_yaml(args.registry)
    records, coverage = FundamentalCoverageProfiler(
        dataset,
        sector_registry=registry,
    ).analyze(
        generated_at=collected_at,
        as_of=collected_at,
    )

    base_report = audit_historical_backtest_readiness(
        dataset,
        coverage,
        generated_at=collected_at,
        coverage_records=records,
        as_of=collected_at,
    )
    report = integrate_corporate_action_readiness(
        base_report,
        corporate_action_evidence,
        audited_raw_price_fingerprint_sha256=audited_raw_price_fingerprint,
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        report.model_dump_json(indent=2) + "\n",
        encoding="utf-8",
    )

    if report.strict_historical_backtest_data_ready:
        raise RuntimeError(
            "historical readiness unexpectedly passed despite known source-contract blockers"
        )
    missing_expected = sorted(EXPECTED_SOURCE_BLOCKERS - set(report.blockers))
    if missing_expected:
        raise RuntimeError(
            "historical readiness failed to expose expected blockers: "
            + ", ".join(missing_expected)
        )
    if SECTOR_ROUTING_NOT_POINT_IN_TIME in report.blockers:
        raise RuntimeError(
            "persisted FCA historical routes did not replace current-B3 routing blocker"
        )
    if report.current_b3_fallback_used:
        raise RuntimeError("historical readiness used a forbidden current-B3 fallback")
    if report.historical_route_gap_count:
        raise RuntimeError(
            "historical readiness smoke has persisted route gaps: "
            + ", ".join(
                f"{gap.company_id}:{gap.fiscal_year}"
                for gap in report.historical_model_route_gaps
            )
        )
    if (
        report.historical_route_company_years
        != report.historical_route_admissible_company_years
    ):
        raise RuntimeError("historical route admissibility count is inconsistent")
    if report.bank_profiles < 1:
        raise RuntimeError("historical readiness smoke did not resolve any IFData bank profile")
    if report.expected_ticker_years != report.security_ticker_years:
        raise RuntimeError("historical security history is incomplete for bounded smoke tickers")
    if report.expected_ticker_years != report.price_ticker_years:
        raise RuntimeError("historical price history is incomplete for bounded smoke tickers")

    expected_gap_count = (
        report.fundamental_company_years
        - report.point_in_time_critical_complete_company_years
    )
    if report.fundamental_point_in_time_gap_count != expected_gap_count:
        raise RuntimeError("fundamental PIT gap count is inconsistent with coverage summary")
    if not report.fundamental_point_in_time_gap_details_complete:
        raise RuntimeError("fundamental PIT gap details were not fully attributed")
    if len(report.fundamental_point_in_time_gaps) != expected_gap_count:
        raise RuntimeError("fundamental PIT gap details are incomplete")

    if FUNDAMENTAL_POINT_IN_TIME_COVERAGE_INCOMPLETE in report.blockers:
        causes = {
            cause
            for gap in report.fundamental_point_in_time_gaps
            for cause in gap.causes
        }
        if SPECIALIZED_EVIDENCE_NOT_POINT_IN_TIME not in causes:
            raise RuntimeError(
                "bounded bank sample has a fundamental PIT gap without specialized "
                "evidence attribution"
            )

    if corporate_action_evidence is not None:
        if not report.corporate_action_evidence_attached:
            raise RuntimeError("corporate-action integration evidence was not attached")
        if not report.corporate_action_m15_event_aware_path_validated:
            raise RuntimeError("bounded integration evidence did not validate the M15 event path")
        if report.corporate_action_strict_event_aware_backtest_ready:
            raise RuntimeError("diagnostic corporate-action evidence unexpectedly became strict")
        if report.price_treatment_mode != PRICE_TREATMENT_EVENT_AWARE_M15_DIAGNOSTIC_ONLY:
            raise RuntimeError(
                "unadjusted price treatment did not expose diagnostic event-aware mode"
            )
        if (
            not report.corporate_action_evidence_matches_requested_universe
            and CORPORATE_ACTION_EVIDENCE_UNIVERSE_INCOMPLETE not in report.blockers
        ):
            raise RuntimeError("corporate-action evidence scope mismatch was not fail-closed")
        if report.corporate_action_evidence_matches_raw_prices:
            raise RuntimeError("unrelated event evidence matched audited raw-price provenance")
        if CORPORATE_ACTION_PRICE_PROVENANCE_MISMATCH not in report.blockers:
            raise RuntimeError("raw-price provenance mismatch was not fail-closed")
        if report.audited_raw_price_fingerprint_sha256 != audited_raw_price_fingerprint:
            raise RuntimeError("audited raw-price fingerprint was not preserved in readiness")


if __name__ == "__main__":
    main()
