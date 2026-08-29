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
    SectorClassificationRecord,
    SecurityRecord,
)
from ultimate_stock_analyzer.fundamentals.contracts import GENERAL_CORPORATE_CONTRACT
from ultimate_stock_analyzer.fundamentals.cvm_accounts import GENERAL_CORPORATE_FIXED_ACCOUNTS
from ultimate_stock_analyzer.scoring.sector_models import SectorModelRegistry


def _write_rows(run_dir: Path, relative: str, rows, name: str) -> BootstrapArtifact:
    path = run_dir / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wt", encoding="utf-8") as file:
        for row in rows:
            file.write(row.model_dump_json())
            file.write("\n")
    content = path.read_bytes()
    return BootstrapArtifact(
        name=name,
        source="TEST",
        path=relative,
        sha256=hashlib.sha256(content).hexdigest(),
        bytes=len(content),
        rows=len(rows),
        raw=False,
    )


def _bank_lines(collected_at: datetime) -> list[FinancialStatementLine]:
    critical = set(GENERAL_CORPORATE_CONTRACT.critical_inputs)
    output: list[FinancialStatementLine] = []
    for account in GENERAL_CORPORATE_FIXED_ACCOUNTS:
        if account.name not in critical:
            continue
        output.append(
            FinancialStatementLine(
                company_id="cvm:19348",
                cvm_code=19348,
                company_name="Itaú Unibanco Holding S.A.",
                document_type="DFP",
                statement=account.statements[0],
                consolidation_scope="DF Consolidado",
                reference_date=date(2025, 12, 31),
                fiscal_order="ÚLTIMO",
                account_code=account.code,
                account_name=account.name,
                value_brl=100.0,
                version=1,
                available_from=datetime(2026, 2, 10, tzinfo=UTC),
                collected_at=collected_at,
            )
        )
    return output


def test_coverage_profiler_routes_bank_and_requires_specialized_contract(tmp_path: Path) -> None:
    collected_at = datetime(2026, 8, 29, 22, tzinfo=UTC)
    run_dir = tmp_path / "bootstrap" / "bank-sector"
    artifacts = [
        _write_rows(
            run_dir,
            "normalized/cvm/issuers.jsonl.gz",
            [
                IssuerRecord(
                    company_id="cvm:19348",
                    cvm_code=19348,
                    legal_name="Itaú Unibanco Holding S.A.",
                    collected_at=collected_at,
                )
            ],
            "cvm_issuer_master",
        ),
        _write_rows(
            run_dir,
            "normalized/cvm/securities_2025.jsonl.gz",
            [
                SecurityRecord(
                    company_id="cvm:19348",
                    ticker="ITUB4",
                    reference_date=date(2025, 12, 31),
                    collected_at=collected_at,
                )
            ],
            "cvm_security_master",
        ),
        _write_rows(
            run_dir,
            "normalized/cvm/dfp_2025.jsonl.gz",
            _bank_lines(collected_at),
            "cvm_financial_statements",
        ),
        _write_rows(
            run_dir,
            "normalized/b3/industry_classification_current.jsonl.gz",
            [
                SectorClassificationRecord(
                    company_id="cvm:19348",
                    cvm_code=19348,
                    issuer_code="ITUB",
                    trading_name="ITAUUNIBANCO",
                    sector="Financeiro",
                    subsector="Intermediários Financeiros",
                    segment="Bancos",
                    listing_segment="Nível 1",
                    collected_at=collected_at,
                )
            ],
            "b3_sector_classification",
        ),
    ]
    manifest = PublicDataBootstrapManifest(
        run_id="bank-sector",
        status="COMPLETE",
        started_at=collected_at,
        completed_at=collected_at,
        start_year=2025,
        end_year=2025,
        requested_tickers=["ITUB4"],
        statements=["BPA", "BPP", "DRE", "DFC_MI"],
        includes_current_sector_classification=True,
        artifacts=artifacts,
    )
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "manifest.json").write_text(manifest.model_dump_json(), encoding="utf-8")

    registry = SectorModelRegistry.from_yaml("config/scoring/sector_registry_v0.6.yml")
    records, summary = FundamentalCoverageProfiler(
        BootstrapDataset(run_dir),
        sector_registry=registry,
    ).analyze(generated_at=collected_at)

    assert len(records) == 1
    record = records[0]
    assert record.sector_model_id == "banks"
    assert record.sector_model_is_fallback is False
    assert record.applicability == "SPECIALIZED_ACCOUNTING_CONTRACT_REQUIRED"
    assert record.sector_classification_point_in_time_eligible is False
    assert summary.applicability == "CURRENT_SECTOR_MODEL_RESOLVED"
    assert summary.resolved_sector_model_company_years == 1
    assert summary.specialized_contract_required_company_years == 1
    assert summary.sector_model_counts == {"banks": 1}
