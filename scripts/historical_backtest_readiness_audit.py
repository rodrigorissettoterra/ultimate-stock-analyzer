from __future__ import annotations

import argparse
from datetime import UTC, datetime
from pathlib import Path

from ultimate_stock_analyzer.backtesting.readiness import (
    BANK_EVIDENCE_NOT_POINT_IN_TIME,
    PRICE_SERIES_UNADJUSTED_FOR_CORPORATE_ACTIONS,
    SECTOR_ROUTING_NOT_POINT_IN_TIME,
    audit_historical_backtest_readiness,
)
from ultimate_stock_analyzer.bootstrap.coverage import FundamentalCoverageProfiler
from ultimate_stock_analyzer.bootstrap.dataset import BootstrapDataset
from ultimate_stock_analyzer.bootstrap.public_data import (
    PublicDataBootstrapPlan,
    PublicDataBootstrapService,
)
from ultimate_stock_analyzer.scoring.sector_models import SectorModelRegistry


DEFAULT_REGISTRY = "config/scoring/sector_registry_v0.6.yml"
EXPECTED_SOURCE_BLOCKERS = {
    SECTOR_ROUTING_NOT_POINT_IN_TIME,
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
        "--output",
        default="historical-backtest-readiness.json",
    )
    args = parser.parse_args()

    collected_at = datetime.now(UTC)
    tickers = tuple(args.ticker)
    if not tickers:
        raise ValueError("readiness audit requires at least one bounded ticker")

    plan = PublicDataBootstrapPlan(
        start_year=args.start_year,
        end_year=args.end_year,
        tickers=tickers,
        include_current_sector_classification=True,
        include_bank_ifdata=True,
    )
    data_dir = Path(args.data_dir)
    manifest = PublicDataBootstrapService(data_dir).run(
        plan,
        collected_at=collected_at,
    )
    dataset = BootstrapDataset(data_dir / "bootstrap" / manifest.run_id)
    registry = SectorModelRegistry.from_yaml(args.registry)
    _records, coverage = FundamentalCoverageProfiler(
        dataset,
        sector_registry=registry,
    ).analyze(generated_at=collected_at)

    report = audit_historical_backtest_readiness(
        dataset,
        coverage,
        generated_at=collected_at,
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        report.model_dump_json(indent=2) + "\n",
        encoding="utf-8",
    )

    # The current public-source contract is intentionally expected to fail strict
    # PIT readiness for these reasons. The smoke succeeds only when the audit
    # detects them instead of silently treating latest-state/unadjusted evidence
    # as historical truth.
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
    if report.bank_profiles < 1:
        raise RuntimeError("historical readiness smoke did not resolve any IFData bank profile")
    if report.expected_ticker_years != report.security_ticker_years:
        raise RuntimeError("historical security history is incomplete for bounded smoke tickers")
    if report.expected_ticker_years != report.price_ticker_years:
        raise RuntimeError("historical price history is incomplete for bounded smoke tickers")


if __name__ == "__main__":
    main()
