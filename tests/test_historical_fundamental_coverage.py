from __future__ import annotations

import gzip
import hashlib
import json
from datetime import UTC, date, datetime
from pathlib import Path

from pydantic import BaseModel

from ultimate_stock_analyzer.backtesting.historical_model_routes import (
    HISTORICAL_MODEL_ROUTE_NOT_YET_AVAILABLE,
    HistoricalModelRoute,
)
from ultimate_stock_analyzer.bootstrap.coverage import (
    HISTORICAL_MODEL_ROUTE_UNSUPPORTED_MODEL,
    FundamentalCoverageProfiler,
)
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

NOW = datetime(2026, 9, 4, tzinfo=UTC)
CUTOFF = datetime(2026, 1, 15, tzinfo=UTC)


def test_historical_profiler_uses_persisted_route_and_ignores_current_b3(
    tmp_path: Path,
) -> None:
    run_dir = _run(
        tmp_path,
        route_model_id="commodities",
        route_available_from=datetime(2025, 3, 1, tzinfo=UTC),
        include_current_b3=True,
    )
    registry = SectorModelRegistry.from_yaml("config/scoring/sector_registry_v0.6.yml")

    records, summary = FundamentalCoverageProfiler(
        BootstrapDataset(run_dir),
        sector_registry=registry,
    ).analyze(
        generated_at=NOW,
        as_of=CUTOFF,
    )

    assert len(records) == 1
    record = records[0]
    assert record.sector_routing_source == "HISTORICAL_MODEL_ROUTE"
    assert record.sector_model_id == "commodities"
    assert record.historical_model_route_admissible is True
    assert record.historical_model_route_blockers == []
    assert record.sector is None
    assert record.sector_classification_point_in_time_eligible is None
    assert record.point_in_time_critical_coverage == 1.0
    assert summary.applicability == "HISTORICAL_SECTOR_MODEL_RESOLVED"
    assert summary.historical_route_company_years == 1
    assert summary.historical_route_admissible_company_years == 1
    assert summary.historical_route_gap_company_years == 0


def test_historical_profiler_hides_late_restatement_until_available(
    tmp_path: Path,
) -> None:
    run_dir = _run(
        tmp_path,
        route_model_id="commodities",
        route_available_from=datetime(2025, 3, 1, tzinfo=UTC),
        include_late_restatement=True,
    )
    registry = SectorModelRegistry.from_yaml("config/scoring/sector_registry_v0.6.yml")

    records, _summary = FundamentalCoverageProfiler(
        BootstrapDataset(run_dir),
        sector_registry=registry,
    ).analyze(
        generated_at=NOW,
        as_of=CUTOFF,
    )

    record = records[0]
    assert record.critical_coverage == 1.0
    assert record.point_in_time_critical_coverage == 1.0
    assert record.not_yet_available_critical == []
    assert all("revenue-v2" not in source for source in record.source_documents)
    assert record.latest_available_from is not None
    assert record.latest_available_from <= CUTOFF


def test_historical_profiler_fails_closed_when_route_is_not_yet_available(
    tmp_path: Path,
) -> None:
    run_dir = _run(
        tmp_path,
        route_model_id="commodities",
        route_available_from=datetime(2026, 6, 1, tzinfo=UTC),
    )
    registry = SectorModelRegistry.from_yaml("config/scoring/sector_registry_v0.6.yml")

    records, summary = FundamentalCoverageProfiler(
        BootstrapDataset(run_dir),
        sector_registry=registry,
    ).analyze(
        generated_at=NOW,
        as_of=CUTOFF,
    )

    record = records[0]
    assert record.historical_model_route_admissible is False
    assert record.historical_model_route_blockers == [
        HISTORICAL_MODEL_ROUTE_NOT_YET_AVAILABLE
    ]
    assert record.sector_model_id is None
    assert record.historical_model_route_model_id == "commodities"
    assert record.point_in_time_critical_coverage == 0.0
    assert summary.historical_route_gap_company_years == 1


def test_historical_profiler_never_maps_abstention_route_to_general_contract(
    tmp_path: Path,
) -> None:
    run_dir = _run(
        tmp_path,
        route_model_id="itsa_holding_abstain",
        route_available_from=datetime(2025, 3, 1, tzinfo=UTC),
    )
    registry = SectorModelRegistry.from_yaml("config/scoring/sector_registry_v0.6.yml")

    records, _summary = FundamentalCoverageProfiler(
        BootstrapDataset(run_dir),
        sector_registry=registry,
    ).analyze(
        generated_at=NOW,
        as_of=CUTOFF,
    )

    record = records[0]
    assert record.historical_model_route_admissible is False
    assert HISTORICAL_MODEL_ROUTE_UNSUPPORTED_MODEL in (
        record.historical_model_route_blockers
    )
    assert record.historical_model_route_model_id == "itsa_holding_abstain"
    assert record.sector_model_id is None
    assert record.applicability == "UNRESOLVED_SECTOR_MODEL"
    assert record.point_in_time_critical_coverage == 0.0


def _run(
    tmp_path: Path,
    *,
    route_model_id: str,
    route_available_from: datetime,
    include_current_b3: bool = False,
    include_late_restatement: bool = False,
) -> Path:
    run_dir = tmp_path / "bootstrap" / "historical-coverage"
    issuer = IssuerRecord(
        company_id="cvm:1",
        cvm_code=1,
        legal_name="Teste S.A.",
        collected_at=NOW,
    )
    security = SecurityRecord(
        company_id="cvm:1",
        ticker="TEST3",
        trading_start=date(2020, 1, 1),
        reference_date=date(2025, 12, 31),
        available_from=datetime(2025, 1, 2, tzinfo=UTC),
        collected_at=NOW,
    )
    statements = _statement_lines(include_late_restatement=include_late_restatement)
    route = HistoricalModelRoute(
        company_id="cvm:1",
        fiscal_year=2025,
        model_id=route_model_id,
        available_from=route_available_from,
        evidence_source="CVM_FCA",
        source_document="https://dados.cvm.gov.br/test#ID_Documento=1:Versao=1",
        evidence_sha256="a" * 64,
        mapping_rule_version="test+sector-registry/0.6.3",
        point_in_time_eligible=True,
        reason="test historical route",
    )

    artifacts = [
        _write_jsonl(
            run_dir,
            "normalized/cvm/issuers.jsonl.gz",
            [issuer],
            name="cvm_issuer_master",
        ),
        _write_jsonl(
            run_dir,
            "normalized/cvm/securities_2025.jsonl.gz",
            [security],
            name="cvm_security_master",
            year=2025,
        ),
        _write_jsonl(
            run_dir,
            "normalized/cvm/dfp_2025.jsonl.gz",
            statements,
            name="cvm_financial_statements",
            year=2025,
        ),
        _write_jsonl(
            run_dir,
            "normalized/cvm/historical_model_routes_2025.jsonl.gz",
            [route],
            name="cvm_historical_model_route",
            year=2025,
        ),
    ]
    if include_current_b3:
        artifacts.append(
            _write_jsonl(
                run_dir,
                "normalized/b3/industry_classification_current.jsonl.gz",
                [
                    SectorClassificationRecord(
                        company_id="cvm:1",
                        cvm_code=1,
                        issuer_code="TEST",
                        trading_name="TESTE",
                        sector="Financeiro",
                        subsector="Intermediários Financeiros",
                        segment="Bancos",
                        collected_at=NOW,
                        point_in_time_eligible=False,
                    )
                ],
                name="b3_sector_classification",
            )
        )

    manifest = PublicDataBootstrapManifest(
        run_id="historical-coverage",
        status="COMPLETE",
        started_at=NOW,
        completed_at=NOW,
        start_year=2025,
        end_year=2025,
        requested_tickers=["TEST3"],
        statements=["BPA", "BPP", "DRE", "DFC_MI"],
        includes_current_sector_classification=include_current_b3,
        artifacts=artifacts,
    )
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "manifest.json").write_text(
        manifest.model_dump_json(indent=2),
        encoding="utf-8",
    )
    return run_dir


def _statement_lines(
    *,
    include_late_restatement: bool,
) -> list[FinancialStatementLine]:
    critical = set(GENERAL_CORPORATE_CONTRACT.critical_inputs)
    lines: list[FinancialStatementLine] = []
    for account in GENERAL_CORPORATE_FIXED_ACCOUNTS:
        if account.name not in critical:
            continue
        lines.append(
            FinancialStatementLine(
                company_id="cvm:1",
                cvm_code=1,
                company_name="Teste S.A.",
                document_type="DFP",
                statement=account.statements[0],
                consolidation_scope="DF Consolidado",
                reference_date=date(2025, 12, 31),
                fiscal_order="ÚLTIMO",
                account_code=account.code,
                account_name=account.name,
                value_brl=100.0,
                version=1,
                document_id=100,
                available_from=datetime(2025, 3, 1, tzinfo=UTC),
                collected_at=NOW,
                source_document=f"{account.name}-v1",
            )
        )
        if include_late_restatement and account.name == "revenue":
            lines.append(
                FinancialStatementLine(
                    company_id="cvm:1",
                    cvm_code=1,
                    company_name="Teste S.A.",
                    document_type="DFP",
                    statement=account.statements[0],
                    consolidation_scope="DF Consolidado",
                    reference_date=date(2025, 12, 31),
                    fiscal_order="ÚLTIMO",
                    account_code=account.code,
                    account_name=account.name,
                    value_brl=999.0,
                    version=2,
                    document_id=200,
                    available_from=datetime(2026, 3, 1, tzinfo=UTC),
                    collected_at=NOW,
                    source_document="revenue-v2",
                )
            )
    return lines


def _write_jsonl(
    run_dir: Path,
    relative_path: str,
    rows: list[BaseModel],
    *,
    name: str,
    year: int | None = None,
) -> BootstrapArtifact:
    path = run_dir / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wt", encoding="utf-8", newline="\n") as file:
        for row in rows:
            file.write(json.dumps(row.model_dump(mode="json"), sort_keys=True))
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
