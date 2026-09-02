from __future__ import annotations

import gzip
import hashlib
import json
from datetime import UTC, date, datetime
from pathlib import Path

from pydantic import BaseModel

from ultimate_stock_analyzer.backtesting.readiness import (
    BANK_EVIDENCE_NOT_POINT_IN_TIME,
    FUNDAMENTAL_POINT_IN_TIME_COVERAGE_INCOMPLETE,
    PRICE_SERIES_UNADJUSTED_FOR_CORPORATE_ACTIONS,
    SECTOR_ROUTING_NOT_POINT_IN_TIME,
    audit_historical_backtest_readiness,
)
from ultimate_stock_analyzer.bootstrap.coverage import FundamentalCoverageSummary
from ultimate_stock_analyzer.bootstrap.dataset import BootstrapDataset
from ultimate_stock_analyzer.bootstrap.public_data import (
    BootstrapArtifact,
    PublicDataBootstrapManifest,
)
from ultimate_stock_analyzer.domain.master import (
    BankPrudentialAnnualRecord,
    SectorClassificationRecord,
    SecurityRecord,
)

NOW = datetime(2026, 9, 1, tzinfo=UTC)


def _write_jsonl(
    run_dir: Path,
    relative_path: str,
    rows: list[BaseModel | dict[str, object]],
    *,
    name: str,
    year: int | None = None,
) -> BootstrapArtifact:
    path = run_dir / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wt", encoding="utf-8") as file:
        for row in rows:
            if isinstance(row, BaseModel):
                payload = row.model_dump_json()
            else:
                payload = json.dumps(row, separators=(",", ":"), sort_keys=True)
            file.write(payload)
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


def _classification(*, pit: bool) -> SectorClassificationRecord:
    return SectorClassificationRecord(
        company_id="cvm:1",
        cvm_code=1,
        issuer_code="TEST",
        trading_name="Teste",
        sector="Petróleo, Gás e Biocombustíveis",
        subsector="Petróleo, Gás e Biocombustíveis",
        segment="Exploração, Refino e Distribuição",
        collected_at=NOW,
        point_in_time_eligible=pit,
    )


def _bank_profile(*, pit: bool) -> BankPrudentialAnnualRecord:
    return BankPrudentialAnnualRecord(
        company_id="cvm:1",
        cvm_code=1,
        cnpj_root="12345678",
        fiscal_year=2025,
        reference_date=date(2025, 12, 31),
        ifdata_cod_inst="C0000001",
        ifdata_name="Banco Teste",
        collected_at=NOW,
        point_in_time_eligible=pit,
    )


def _coverage(*, pit_complete: int) -> FundamentalCoverageSummary:
    return FundamentalCoverageSummary(
        bootstrap_run_id="readiness-test",
        bootstrap_manifest_sha256="test",
        generated_at=NOW,
        applicability="CURRENT_SECTOR_MODEL_RESOLVED",
        companies=1,
        company_years=2,
        mapped_tickers=1,
        critical_complete_company_years=2,
        point_in_time_critical_complete_company_years=pit_complete,
        longitudinal_pair_ready_company_years=1 if pit_complete == 2 else 0,
        resolved_sector_model_company_years=2,
        bank_contract_available_company_years=1 if pit_complete < 2 else 0,
        specialized_contract_required_company_years=0,
        general_corporate_applicable_company_years=1,
        mean_critical_coverage=1.0,
        mean_total_coverage=1.0,
        coverage_buckets={"critical_100pct": 2},
        sector_model_counts={"general_corporate": 2},
        warnings=[],
    )


def _dataset(
    tmp_path: Path,
    *,
    pit_sector: bool,
    include_non_pit_bank: bool,
    adjusted_prices: bool,
) -> BootstrapDataset:
    run_dir = tmp_path / "bootstrap" / "readiness-test"
    artifacts: list[BootstrapArtifact] = []
    for year in (2024, 2025):
        security = SecurityRecord(
            company_id="cvm:1",
            ticker="TEST3",
            trading_start=date(2020, 1, 1),
            reference_date=date(year, 12, 31),
            available_from=datetime(year, 1, 1, tzinfo=UTC),
            collected_at=NOW,
        )
        artifacts.append(
            _write_jsonl(
                run_dir,
                f"normalized/cvm/securities_{year}.jsonl.gz",
                [security],
                name="cvm_security_master",
                year=year,
            )
        )
        artifacts.append(
            _write_jsonl(
                run_dir,
                f"normalized/b3/cotahist_{year}.jsonl.gz",
                [
                    {
                        "ticker": "TEST3",
                        "trade_date": f"{year}-12-30",
                        "open": 10.0,
                        "high": 11.0,
                        "low": 9.0,
                        "close": 10.5,
                        "volume": 1000.0,
                        "trades": 10,
                        "quantity": 100,
                        "adjusted_close": 10.5 if adjusted_prices else None,
                    }
                ],
                name="b3_cotahist",
                year=year,
            )
        )

    artifacts.append(
        _write_jsonl(
            run_dir,
            "normalized/b3/industry_classification_current.jsonl.gz",
            [_classification(pit=pit_sector)],
            name="b3_sector_classification",
        )
    )
    if include_non_pit_bank:
        artifacts.append(
            _write_jsonl(
                run_dir,
                "normalized/bcb/ifdata_bank_profiles_2025.jsonl.gz",
                [_bank_profile(pit=False)],
                name="bcb_ifdata_bank_profile",
                year=2025,
            )
        )

    manifest = PublicDataBootstrapManifest(
        run_id="readiness-test",
        status="COMPLETE",
        started_at=NOW,
        completed_at=NOW,
        start_year=2024,
        end_year=2025,
        requested_tickers=["TEST3"],
        statements=["BPA", "BPP", "DRE"],
        includes_current_sector_classification=True,
        includes_bank_ifdata=include_non_pit_bank,
        artifacts=artifacts,
    )
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "manifest.json").write_text(
        manifest.model_dump_json(indent=2),
        encoding="utf-8",
    )
    return BootstrapDataset(run_dir)


def test_readiness_fails_closed_on_latest_state_and_unadjusted_evidence(
    tmp_path: Path,
) -> None:
    dataset = _dataset(
        tmp_path,
        pit_sector=False,
        include_non_pit_bank=True,
        adjusted_prices=False,
    )
    report = audit_historical_backtest_readiness(
        dataset,
        _coverage(pit_complete=1),
        generated_at=NOW,
    )

    assert not report.strict_historical_backtest_data_ready
    assert not report.walk_forward_data_ready
    assert report.expected_ticker_years == 2
    assert report.security_ticker_years == 2
    assert report.price_ticker_years == 2
    assert report.missing_security_ticker_years == []
    assert report.missing_price_ticker_years == []
    assert report.unadjusted_price_bars == 2
    assert set(report.blockers) >= {
        SECTOR_ROUTING_NOT_POINT_IN_TIME,
        BANK_EVIDENCE_NOT_POINT_IN_TIME,
        FUNDAMENTAL_POINT_IN_TIME_COVERAGE_INCOMPLETE,
        PRICE_SERIES_UNADJUSTED_FOR_CORPORATE_ACTIONS,
    }


def test_readiness_can_pass_when_evidence_is_point_in_time_and_prices_are_adjusted(
    tmp_path: Path,
) -> None:
    dataset = _dataset(
        tmp_path,
        pit_sector=True,
        include_non_pit_bank=False,
        adjusted_prices=True,
    )
    report = audit_historical_backtest_readiness(
        dataset,
        _coverage(pit_complete=2),
        generated_at=NOW,
    )

    assert report.blockers == []
    assert report.strict_historical_backtest_data_ready
    assert report.walk_forward_data_ready
    assert report.point_in_time_eligible
    assert not report.weight_promotion_evaluated
    assert report.adjusted_price_bars == 2
    assert report.unadjusted_price_bars == 0
