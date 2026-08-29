from __future__ import annotations

import gzip
import hashlib
from datetime import UTC, date, datetime
from pathlib import Path

from ultimate_stock_analyzer.bootstrap.coverage import FundamentalCoverageProfiler
from ultimate_stock_analyzer.bootstrap.dataset import BootstrapDataset
from ultimate_stock_analyzer.bootstrap.public_data import (
    BootstrapArtifact,
    PublicDataBootstrapManifest,
)
from ultimate_stock_analyzer.domain.master import (
    FinancialStatementLine,
    IssuerRecord,
    SecurityRecord,
)
from ultimate_stock_analyzer.fundamentals.contracts import GENERAL_CORPORATE_CONTRACT
from ultimate_stock_analyzer.fundamentals.cvm_accounts import GENERAL_CORPORATE_FIXED_ACCOUNTS


def _write_jsonl(path: Path, rows, *, name: str, year: int | None = None) -> BootstrapArtifact:
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wt", encoding="utf-8") as file:
        for row in rows:
            file.write(row.model_dump_json())
            file.write("\n")
    content = path.read_bytes()
    return BootstrapArtifact(
        name=name,
        source="TEST",
        path=path.relative_to(path.parents[2]).as_posix(),
        sha256=hashlib.sha256(content).hexdigest(),
        bytes=len(content),
        rows=len(rows),
        reference_year=year,
        raw=False,
    )


def _statement_lines(year: int, *, untimed: str | None = None) -> list[FinancialStatementLine]:
    critical = set(GENERAL_CORPORATE_CONTRACT.critical_inputs)
    lines: list[FinancialStatementLine] = []
    for account in GENERAL_CORPORATE_FIXED_ACCOUNTS:
        if account.name not in critical:
            continue
        statement = account.statements[0]
        lines.append(
            FinancialStatementLine(
                company_id="cvm:1",
                cvm_code=1,
                company_name="Teste S.A.",
                document_type="DFP",
                statement=statement,
                consolidation_scope="DF Consolidado",
                reference_date=date(year, 12, 31),
                fiscal_order="ÚLTIMO",
                account_code=account.code,
                account_name=account.name,
                value_brl=100.0,
                version=1,
                available_from=(
                    None
                    if account.name == untimed
                    else datetime(year + 1, 3, 1, tzinfo=UTC)
                ),
                collected_at=datetime(2026, 8, 29, tzinfo=UTC),
                source_document=f"dfp_{statement}_{year}.csv",
            )
        )
    return lines


def _bootstrap_run(tmp_path: Path) -> Path:
    run_dir = tmp_path / "bootstrap" / "coverage-test"
    issuer = IssuerRecord(
        company_id="cvm:1",
        cvm_code=1,
        legal_name="Teste S.A.",
        collected_at=datetime(2026, 8, 29, tzinfo=UTC),
    )
    securities = [
        SecurityRecord(
            company_id="cvm:1",
            ticker="TEST3",
            trading_start=date(2020, 1, 1),
            collected_at=datetime(2026, 8, 29, tzinfo=UTC),
        )
    ]
    artifacts = [
        _write_jsonl(
            run_dir / "normalized/cvm/issuers.jsonl.gz",
            [issuer],
            name="cvm_issuer_master",
        ),
        _write_jsonl(
            run_dir / "normalized/cvm/securities_2023.jsonl.gz",
            securities,
            name="cvm_security_master",
            year=2023,
        ),
        _write_jsonl(
            run_dir / "normalized/cvm/dfp_2023.jsonl.gz",
            _statement_lines(2023),
            name="cvm_financial_statements",
            year=2023,
        ),
        _write_jsonl(
            run_dir / "normalized/cvm/dfp_2024.jsonl.gz",
            _statement_lines(2024, untimed="revenue"),
            name="cvm_financial_statements",
            year=2024,
        ),
    ]
    manifest = PublicDataBootstrapManifest(
        run_id="coverage-test",
        status="COMPLETE",
        started_at=datetime(2026, 8, 29, tzinfo=UTC),
        completed_at=datetime(2026, 8, 29, tzinfo=UTC),
        start_year=2023,
        end_year=2024,
        requested_tickers=["TEST3"],
        statements=["BPA", "BPP", "DRE", "DFC_MI"],
        artifacts=artifacts,
    )
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "manifest.json").write_text(manifest.model_dump_json(), encoding="utf-8")
    return run_dir


def test_profiler_separates_account_coverage_from_point_in_time_coverage(tmp_path: Path) -> None:
    dataset = BootstrapDataset(_bootstrap_run(tmp_path))
    records, summary = FundamentalCoverageProfiler(dataset).analyze(
        generated_at=datetime(2026, 8, 29, tzinfo=UTC)
    )

    assert len(records) == 2
    by_year = {record.fiscal_year: record for record in records}
    assert by_year[2023].critical_coverage == 1.0
    assert by_year[2023].point_in_time_critical_coverage == 1.0
    assert by_year[2024].critical_coverage == 1.0
    assert by_year[2024].point_in_time_critical_coverage < 1.0
    assert by_year[2024].untimed_critical == ["revenue"]
    assert by_year[2024].has_prior_fiscal_year
    assert not by_year[2024].longitudinal_pair_ready
    assert summary.critical_complete_company_years == 2
    assert summary.point_in_time_critical_complete_company_years == 1
    assert summary.longitudinal_pair_ready_company_years == 0
    assert summary.applicability == "UNRESOLVED_SECTOR_CLASSIFICATION"


def test_profiler_writes_separate_derived_output(tmp_path: Path) -> None:
    dataset = BootstrapDataset(_bootstrap_run(tmp_path))
    output_root = tmp_path / "derived"
    summary = FundamentalCoverageProfiler(dataset).write(
        output_root,
        generated_at=datetime(2026, 8, 29, tzinfo=UTC),
    )
    output_dir = output_root / "coverage" / "coverage-test"
    assert summary.company_years == 2
    assert (output_dir / "fundamental_coverage.jsonl.gz").is_file()
    assert (output_dir / "summary.json").is_file()
