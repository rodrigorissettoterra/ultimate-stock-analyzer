from __future__ import annotations

import gzip
import hashlib
import json
from datetime import UTC, date, datetime
from pathlib import Path

from ultimate_stock_analyzer.backtesting.historical_model_routes import (
    HISTORICAL_MODEL_ROUTE_NOT_YET_AVAILABLE,
)
from ultimate_stock_analyzer.backtesting.readiness import (
    PRICE_SERIES_UNADJUSTED_FOR_CORPORATE_ACTIONS,
    SECTOR_ROUTING_NOT_POINT_IN_TIME,
    SECTOR_ROUTING_UNAVAILABLE,
    audit_historical_backtest_readiness,
)
from ultimate_stock_analyzer.bootstrap.coverage import (
    FundamentalCoverageRecord,
    FundamentalCoverageSummary,
)
from ultimate_stock_analyzer.bootstrap.dataset import BootstrapDataset
from ultimate_stock_analyzer.bootstrap.public_data import (
    BootstrapArtifact,
    PublicDataBootstrapManifest,
)

AS_OF = datetime(2026, 1, 15, tzinfo=UTC)


def test_historical_readiness_uses_route_decisions_without_current_b3_fallback(
    tmp_path: Path,
) -> None:
    dataset = _dataset(tmp_path)
    record = _record(route_admissible=True, route_blockers=[], pit_coverage=1.0)
    coverage = _summary(route_admissible=1, route_gaps=0, pit_complete=1)

    report = audit_historical_backtest_readiness(
        dataset,
        coverage,
        generated_at=AS_OF,
        coverage_records=[record],
        as_of=AS_OF,
    )

    assert SECTOR_ROUTING_UNAVAILABLE not in report.blockers
    assert SECTOR_ROUTING_NOT_POINT_IN_TIME not in report.blockers
    assert report.historical_route_company_years == 1
    assert report.historical_route_admissible_company_years == 1
    assert report.historical_route_gap_count == 0
    assert report.historical_model_route_gaps == []
    assert report.current_b3_fallback_used is False
    assert PRICE_SERIES_UNADJUSTED_FOR_CORPORATE_ACTIONS in report.blockers


def test_historical_readiness_attributes_future_route_without_general_fallback(
    tmp_path: Path,
) -> None:
    dataset = _dataset(tmp_path)
    record = _record(
        route_admissible=False,
        route_blockers=[HISTORICAL_MODEL_ROUTE_NOT_YET_AVAILABLE],
        pit_coverage=0.0,
    )
    coverage = _summary(route_admissible=0, route_gaps=1, pit_complete=0)

    report = audit_historical_backtest_readiness(
        dataset,
        coverage,
        generated_at=AS_OF,
        coverage_records=[record],
        as_of=AS_OF,
    )

    assert HISTORICAL_MODEL_ROUTE_NOT_YET_AVAILABLE in report.blockers
    assert report.historical_route_gap_count == 1
    gap = report.historical_model_route_gaps[0]
    assert gap.company_id == "cvm:1"
    assert gap.fiscal_year == 2025
    assert gap.model_id == "commodities"
    assert gap.blockers == [HISTORICAL_MODEL_ROUTE_NOT_YET_AVAILABLE]
    assert HISTORICAL_MODEL_ROUTE_NOT_YET_AVAILABLE in (
        report.fundamental_point_in_time_gaps[0].causes
    )


def _record(
    *,
    route_admissible: bool,
    route_blockers: list[str],
    pit_coverage: float,
) -> FundamentalCoverageRecord:
    return FundamentalCoverageRecord(
        company_id="cvm:1",
        cvm_code=1,
        company_name="Teste S.A.",
        tickers=["TEST3"],
        reference_date=date(2025, 12, 31),
        fiscal_year=2025,
        contract="general_corporate_v1",
        applicability=(
            "GENERAL_CORPORATE_APPLICABLE"
            if route_admissible
            else "UNRESOLVED_SECTOR_MODEL"
        ),
        sector_model_id="commodities" if route_admissible else None,
        sector_routing_source="HISTORICAL_MODEL_ROUTE",
        historical_as_of=AS_OF,
        historical_model_route_admissible=route_admissible,
        historical_model_route_blockers=route_blockers,
        historical_model_route_model_id="commodities",
        historical_model_route_available_from=datetime(
            2026 if not route_admissible else 2025,
            6 if not route_admissible else 3,
            1,
            tzinfo=UTC,
        ),
        historical_model_route_evidence_source="CVM_FCA",
        historical_model_route_source_document="TEST",
        extracted_accounts=10,
        critical_coverage=1.0,
        total_coverage=1.0,
        point_in_time_critical_coverage=pit_coverage,
        missing_critical=[],
        missing_supporting=[],
        untimed_critical=[],
        source_documents=["TEST"],
    )


def _summary(
    *,
    route_admissible: int,
    route_gaps: int,
    pit_complete: int,
) -> FundamentalCoverageSummary:
    return FundamentalCoverageSummary(
        bootstrap_run_id="historical-readiness",
        bootstrap_manifest_sha256="a" * 64,
        generated_at=AS_OF,
        applicability=(
            "HISTORICAL_SECTOR_MODEL_RESOLVED"
            if route_admissible
            else "UNRESOLVED_SECTOR_CLASSIFICATION"
        ),
        historical_as_of=AS_OF,
        companies=1,
        company_years=1,
        mapped_tickers=1,
        critical_complete_company_years=1,
        point_in_time_critical_complete_company_years=pit_complete,
        longitudinal_pair_ready_company_years=0,
        resolved_sector_model_company_years=route_admissible,
        historical_route_company_years=1,
        historical_route_admissible_company_years=route_admissible,
        historical_route_gap_company_years=route_gaps,
        bank_contract_available_company_years=0,
        specialized_contract_required_company_years=0,
        general_corporate_applicable_company_years=route_admissible,
        mean_critical_coverage=1.0,
        mean_total_coverage=1.0,
        coverage_buckets={
            "critical_100pct": 1,
            "critical_90_to_99pct": 0,
            "critical_75_to_89pct": 0,
            "critical_below_75pct": 0,
        },
        sector_model_counts={"commodities": 1} if route_admissible else {},
        warnings=[],
    )


def _dataset(tmp_path: Path) -> BootstrapDataset:
    run_dir = tmp_path / "bootstrap" / "historical-readiness"
    security_rows = [
        {
            "company_id": "cvm:1",
            "ticker": "TEST3",
            "reference_date": "2025-12-31",
            "collected_at": AS_OF.isoformat(),
        }
    ]
    price_rows = [
        {
            "ticker": "TEST3",
            "trade_date": "2025-01-02",
            "close": 10.0,
            "adjusted_close": None,
        }
    ]
    artifacts = [
        _write_rows(
            run_dir,
            "normalized/cvm/securities_2025.jsonl.gz",
            security_rows,
            name="cvm_security_master",
            year=2025,
        ),
        _write_rows(
            run_dir,
            "normalized/b3/cotahist_2025.jsonl.gz",
            price_rows,
            name="b3_cotahist",
            year=2025,
        ),
    ]
    manifest = PublicDataBootstrapManifest(
        run_id="historical-readiness",
        status="COMPLETE",
        started_at=AS_OF,
        completed_at=AS_OF,
        start_year=2025,
        end_year=2025,
        requested_tickers=["TEST3"],
        statements=["DRE"],
        artifacts=artifacts,
    )
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "manifest.json").write_text(
        manifest.model_dump_json(indent=2),
        encoding="utf-8",
    )
    return BootstrapDataset(run_dir)


def _write_rows(
    run_dir: Path,
    relative_path: str,
    rows: list[dict[str, object]],
    *,
    name: str,
    year: int,
) -> BootstrapArtifact:
    path = run_dir / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wt", encoding="utf-8", newline="\n") as file:
        for row in rows:
            file.write(json.dumps(row))
            file.write("\n")
    content = path.read_bytes()
    return BootstrapArtifact(
        name=name,
        source="TEST",
        path=relative_path,
        sha256=hashlib.sha256(content).hexdigest(),
        bytes=len(content),
        rows=len(rows),
        reference_year=year,
        raw=False,
    )
