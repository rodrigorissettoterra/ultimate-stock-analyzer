from __future__ import annotations

import gzip
import hashlib
import json
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from ultimate_stock_analyzer.backtesting.cvm_fca_historical_model_routes import (
    FCAHistoricalModelRouteMaterialization,
)
from ultimate_stock_analyzer.backtesting.historical_model_routes import HistoricalModelRoute
from ultimate_stock_analyzer.bootstrap.dataset import BootstrapDataset
from ultimate_stock_analyzer.bootstrap.historical_model_routes import (
    FCAHistoricalModelRouteSource,
    persist_historical_model_routes,
)
from ultimate_stock_analyzer.bootstrap.public_data import (
    BootstrapArtifact,
    PublicDataBootstrapManifest,
)
from ultimate_stock_analyzer.domain.master import SecurityRecord

COLLECTED_AT = datetime(2026, 9, 3, 20, tzinfo=UTC)
REPO_ROOT = Path(__file__).resolve().parents[1]
MAPPING_PATH = REPO_ROOT / "config/backtesting/fca_model_routes_v0.2.yml"
REGISTRY_PATH = REPO_ROOT / "config/scoring/sector_registry_v0.6.yml"
MAPPING_SHA256 = hashlib.sha256(MAPPING_PATH.read_bytes()).hexdigest()


class FakeRouteSource:
    def __init__(self, *, blocked: bool = False) -> None:
        self.blocked = blocked
        self.calls: list[tuple[bytes, int, str, tuple[int, ...]]] = []

    def materialize_archive(
        self,
        archive_content: bytes,
        *,
        collected_at: datetime,
        delivery_year: int,
        source_url: str,
        requested_cvm_codes: tuple[int, ...],
    ) -> FCAHistoricalModelRouteMaterialization:
        assert collected_at == COLLECTED_AT
        self.calls.append(
            (
                archive_content,
                delivery_year,
                source_url,
                requested_cvm_codes,
            )
        )
        if self.blocked:
            return FCAHistoricalModelRouteMaterialization(
                mapping_rule_version="fca-sector-activity-v0.2",
                mapping_source_document=MAPPING_PATH.as_posix(),
                mapping_source_sha256=MAPPING_SHA256,
                sector_registry_version="0.6.3",
                route_count=0,
                routes=(),
                blocked_company_years=(f"cvm:{requested_cvm_codes[0]}:{delivery_year}",),
                unsupported_sector_values=("unsupported",),
                registry_mismatch_values=(),
                blockers=("TEST_BLOCKER",),
            )

        routes = tuple(
            HistoricalModelRoute(
                company_id=f"cvm:{code}",
                fiscal_year=delivery_year,
                model_id="banks" if code == 19348 else "commodities",
                available_from=datetime(delivery_year, 6, 1, tzinfo=UTC),
                evidence_source="CVM_FCA",
                source_document=(
                    f"{source_url}#ID_Documento={code}{delivery_year}:Versao=1"
                ),
                evidence_sha256=hashlib.sha256(
                    f"{code}:{delivery_year}".encode()
                ).hexdigest(),
                mapping_rule_version=(
                    "fca-sector-activity-v0.2+sector-registry/0.6.3"
                ),
                point_in_time_eligible=True,
            )
            for code in requested_cvm_codes
        )
        return FCAHistoricalModelRouteMaterialization(
            mapping_rule_version="fca-sector-activity-v0.2",
            mapping_source_document=MAPPING_PATH.as_posix(),
            mapping_source_sha256=MAPPING_SHA256,
            sector_registry_version="0.6.3",
            route_count=len(routes),
            routes=routes,
            blocked_company_years=(),
            unsupported_sector_values=(),
            registry_mismatch_values=(),
            blockers=(),
        )


def test_persistence_reuses_manifest_bound_fca_and_updates_dataset(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_dir = _build_run(tmp_path, requested_tickers=["PETR4", "VALE3"])
    source = FakeRouteSource()

    updated = _persist_with_fake(run_dir, monkeypatch, source)

    assert len(source.calls) == 2
    assert source.calls[0][0] == b"PK-fca-2024"
    assert source.calls[1][0] == b"PK-fca-2025"
    assert [call[1] for call in source.calls] == [2024, 2025]
    assert all(call[2].startswith("https://dados.cvm.gov.br/") for call in source.calls)
    assert source.calls[0][3] == (4170, 9512)
    assert source.calls[1][3] == (4170, 9512)

    assert updated.counts["historical_model_routes"] == 4
    artifacts = [
        artifact
        for artifact in updated.artifacts
        if artifact.name == "cvm_historical_model_route"
    ]
    assert [artifact.reference_year for artifact in artifacts] == [2024, 2025]
    assert all(artifact.source == "CVM_FCA" and not artifact.raw for artifact in artifacts)

    dataset = BootstrapDataset(run_dir)
    routes = dataset.historical_model_routes()
    assert [(route.company_id, route.fiscal_year, route.model_id) for route in routes] == [
        ("cvm:4170", 2024, "commodities"),
        ("cvm:4170", 2025, "commodities"),
        ("cvm:9512", 2024, "commodities"),
        ("cvm:9512", 2025, "commodities"),
    ]


def test_persistence_accepts_pre_listing_year_without_selected_securities(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_dir = _build_run(tmp_path, requested_tickers=["PETR4", "VALE3"])
    _replace_security_year_with_empty(run_dir, year=2024)
    source = FakeRouteSource()

    updated = _persist_with_fake(run_dir, monkeypatch, source)

    assert [call[1] for call in source.calls] == [2025]
    assert updated.counts["historical_model_routes"] == 2
    artifacts = [
        artifact
        for artifact in updated.artifacts
        if artifact.name == "cvm_historical_model_route"
    ]
    assert [(artifact.reference_year, artifact.rows) for artifact in artifacts] == [
        (2024, 0),
        (2025, 2),
    ]
    routes = BootstrapDataset(run_dir).historical_model_routes()
    assert {(route.company_id, route.fiscal_year) for route in routes} == {
        ("cvm:4170", 2025),
        ("cvm:9512", 2025),
    }


def test_persistence_rejects_unfiltered_bootstrap(tmp_path: Path) -> None:
    run_dir = _build_run(tmp_path, requested_tickers=[])

    with pytest.raises(ValueError, match="explicit ticker filter"):
        persist_historical_model_routes(
            run_dir,
            mapping_path=MAPPING_PATH,
            sector_registry_path=REGISTRY_PATH,
        )


def test_persistence_is_manifest_atomic_when_materialization_blocks(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_dir = _build_run(tmp_path, requested_tickers=["PETR4", "VALE3"])
    manifest_path = run_dir / "manifest.json"
    before = manifest_path.read_bytes()

    with pytest.raises(ValueError, match="TEST_BLOCKER"):
        _persist_with_fake(run_dir, monkeypatch, FakeRouteSource(blocked=True))

    assert manifest_path.read_bytes() == before
    assert not list(
        (run_dir / "normalized/cvm").glob("historical_model_routes_*.jsonl.gz")
    )


def test_persistence_does_not_accept_custom_route_source(tmp_path: Path) -> None:
    run_dir = _build_run(tmp_path, requested_tickers=["PETR4", "VALE3"])

    with pytest.raises(TypeError, match="unexpected keyword argument"):
        persist_historical_model_routes(  # type: ignore[call-arg]
            run_dir,
            route_source=FakeRouteSource(),
        )


def test_persistence_rejects_tampered_mapping_content(tmp_path: Path) -> None:
    run_dir = _build_run(tmp_path, requested_tickers=["PETR4", "VALE3"])
    manifest_path = run_dir / "manifest.json"
    before = manifest_path.read_bytes()
    tampered = tmp_path / "fca_model_routes_tampered.yml"
    tampered.write_bytes(MAPPING_PATH.read_bytes() + b"\n# tampered\n")

    with pytest.raises(ValueError, match="untrusted FCA model-route mapping content"):
        persist_historical_model_routes(
            run_dir,
            mapping_path=tampered,
            sector_registry_path=REGISTRY_PATH,
        )

    assert manifest_path.read_bytes() == before
    assert not list(
        (run_dir / "normalized/cvm").glob("historical_model_routes_*.jsonl.gz")
    )


def test_persistence_rejects_tampered_registry_content(tmp_path: Path) -> None:
    run_dir = _build_run(tmp_path, requested_tickers=["PETR4", "VALE3"])
    manifest_path = run_dir / "manifest.json"
    before = manifest_path.read_bytes()
    tampered = tmp_path / "sector_registry_tampered.yml"
    tampered.write_bytes(REGISTRY_PATH.read_bytes() + b"\n# tampered\n")

    with pytest.raises(ValueError, match="untrusted sector registry content"):
        persist_historical_model_routes(
            run_dir,
            mapping_path=MAPPING_PATH,
            sector_registry_path=tampered,
        )

    assert manifest_path.read_bytes() == before
    assert not list(
        (run_dir / "normalized/cvm").glob("historical_model_routes_*.jsonl.gz")
    )


def _persist_with_fake(
    run_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
    source: FakeRouteSource,
) -> PublicDataBootstrapManifest:
    def _materialize(
        _self: FCAHistoricalModelRouteSource,
        archive_content: bytes,
        *,
        collected_at: datetime,
        delivery_year: int,
        source_url: str,
        requested_cvm_codes: tuple[int, ...],
    ) -> FCAHistoricalModelRouteMaterialization:
        return source.materialize_archive(
            archive_content,
            collected_at=collected_at,
            delivery_year=delivery_year,
            source_url=source_url,
            requested_cvm_codes=requested_cvm_codes,
        )

    monkeypatch.setattr(FCAHistoricalModelRouteSource, "materialize_archive", _materialize)
    return persist_historical_model_routes(
        run_dir,
        mapping_path=MAPPING_PATH,
        sector_registry_path=REGISTRY_PATH,
    )


def _build_run(tmp_path: Path, *, requested_tickers: list[str]) -> Path:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    artifacts: list[BootstrapArtifact] = []
    securities = [
        ("cvm:9512", "PETR4"),
        ("cvm:4170", "VALE3"),
    ]

    for year in (2024, 2025):
        raw_path = run_dir / f"raw/cvm/fca_cia_aberta_{year}.zip"
        raw_path.parent.mkdir(parents=True, exist_ok=True)
        raw_path.write_bytes(f"PK-fca-{year}".encode())
        artifacts.append(
            _artifact(
                run_dir,
                raw_path,
                name="cvm_fca_raw",
                source="CVM_FCA",
                reference_year=year,
                raw=True,
                rows=None,
            )
        )

        selected = securities if requested_tickers else []
        security_rows = [
            SecurityRecord(
                company_id=company_id,
                ticker=ticker,
                reference_date=date(year, 12, 31),
                collected_at=COLLECTED_AT,
            )
            for company_id, ticker in selected
            if ticker in requested_tickers
        ]
        security_path = run_dir / f"normalized/cvm/securities_{year}.jsonl.gz"
        security_path.parent.mkdir(parents=True, exist_ok=True)
        with gzip.open(security_path, "wt", encoding="utf-8", newline="\n") as file:
            for row in security_rows:
                file.write(
                    json.dumps(
                        row.model_dump(mode="json"),
                        ensure_ascii=False,
                        sort_keys=True,
                    )
                )
                file.write("\n")
        artifacts.append(
            _artifact(
                run_dir,
                security_path,
                name="cvm_security_master",
                source="CVM_FCA",
                reference_year=year,
                raw=False,
                rows=len(security_rows),
            )
        )

    manifest = PublicDataBootstrapManifest(
        run_id="historical-route-test",
        status="COMPLETE",
        started_at=COLLECTED_AT,
        completed_at=COLLECTED_AT,
        start_year=2024,
        end_year=2025,
        requested_tickers=requested_tickers,
        statements=["DRE"],
        artifacts=artifacts,
    )
    (run_dir / "manifest.json").write_text(
        manifest.model_dump_json(indent=2),
        encoding="utf-8",
        newline="\n",
    )
    return run_dir


def _replace_security_year_with_empty(run_dir: Path, *, year: int) -> None:
    path = run_dir / f"normalized/cvm/securities_{year}.jsonl.gz"
    with gzip.open(path, "wt", encoding="utf-8", newline="\n"):
        pass

    manifest_path = run_dir / "manifest.json"
    manifest = PublicDataBootstrapManifest.model_validate_json(
        manifest_path.read_text(encoding="utf-8")
    )
    artifacts = []
    for artifact in manifest.artifacts:
        if artifact.name == "cvm_security_master" and artifact.reference_year == year:
            artifacts.append(
                _artifact(
                    run_dir,
                    path,
                    name="cvm_security_master",
                    source="CVM_FCA",
                    reference_year=year,
                    raw=False,
                    rows=0,
                )
            )
        else:
            artifacts.append(artifact)
    updated = PublicDataBootstrapManifest.model_validate(
        {
            **manifest.model_dump(mode="python"),
            "artifacts": [artifact.model_dump(mode="python") for artifact in artifacts],
        }
    )
    manifest_path.write_text(
        updated.model_dump_json(indent=2),
        encoding="utf-8",
        newline="\n",
    )


def _artifact(
    run_dir: Path,
    path: Path,
    *,
    name: str,
    source: str,
    reference_year: int,
    raw: bool,
    rows: int | None,
) -> BootstrapArtifact:
    content = path.read_bytes()
    return BootstrapArtifact(
        name=name,
        source=source,
        path=path.relative_to(run_dir).as_posix(),
        sha256=hashlib.sha256(content).hexdigest(),
        bytes=len(content),
        rows=rows,
        reference_year=reference_year,
        raw=raw,
    )