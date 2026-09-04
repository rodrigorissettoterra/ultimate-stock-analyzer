from __future__ import annotations

import gzip
import hashlib
import json
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

import ultimate_stock_analyzer.bootstrap.historical_model_routes as persistence_module
from ultimate_stock_analyzer.backtesting.cvm_fca_historical_model_routes import (
    FCAHistoricalModelRouteMaterialization,
)
from ultimate_stock_analyzer.backtesting.historical_model_routes import HistoricalModelRoute
from ultimate_stock_analyzer.bootstrap.historical_model_routes import (
    FCAHistoricalModelRouteSource,
    persist_historical_model_routes,
)
from ultimate_stock_analyzer.bootstrap.public_data import (
    BootstrapArtifact,
    PublicDataBootstrapManifest,
)
from ultimate_stock_analyzer.domain.master import SecurityRecord

COLLECTED_AT = datetime(2026, 9, 4, 10, tzinfo=UTC)
REPO_ROOT = Path(__file__).resolve().parents[1]
MAPPING_PATH = REPO_ROOT / "config/backtesting/fca_model_routes_v0.2.yml"
REGISTRY_PATH = REPO_ROOT / "config/scoring/sector_registry_v0.6.yml"
MAPPING_SHA256 = hashlib.sha256(MAPPING_PATH.read_bytes()).hexdigest()


class FakeRouteSource:
    def __init__(self) -> None:
        self.calls: list[bytes] = []

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
        self.calls.append(archive_content)
        routes = tuple(
            HistoricalModelRoute(
                company_id=f"cvm:{code}",
                fiscal_year=delivery_year,
                model_id="commodities",
                available_from=datetime(delivery_year + 1, 3, 1, tzinfo=UTC),
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


def test_persistence_uses_verified_bytes_but_refuses_commit_after_input_changes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_dir, original_manifest = _build_run(tmp_path)
    source = FakeRouteSource()
    _patch_materializer(monkeypatch, source)

    original_snapshot = persistence_module._verified_artifact_snapshot

    def _verify_then_replace(
        run_dir_arg: Path,
        artifact: BootstrapArtifact,
    ) -> persistence_module._VerifiedArtifactSnapshot:
        snapshot = original_snapshot(run_dir_arg, artifact)
        if artifact.name == "cvm_fca_raw":
            snapshot.path.write_bytes(b"tampered-after-verification")
        elif artifact.name == "cvm_security_master":
            with gzip.open(snapshot.path, "wt", encoding="utf-8", newline="\n"):
                pass
        return snapshot

    monkeypatch.setattr(
        persistence_module,
        "_verified_artifact_snapshot",
        _verify_then_replace,
    )

    with pytest.raises(ValueError, match="changed after verification"):
        persist_historical_model_routes(
            run_dir,
            mapping_path=MAPPING_PATH,
            sector_registry_path=REGISTRY_PATH,
        )

    assert source.calls == [b"PK-original-fca"]
    assert (run_dir / "manifest.json").read_bytes() == original_manifest
    assert not list(
        (run_dir / "normalized/cvm").glob("historical_model_routes_*.jsonl.gz")
    )


def test_persistence_recovers_exact_orphan_route_files_after_interruption(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_dir, original_manifest = _build_run(tmp_path)
    source = FakeRouteSource()
    _patch_materializer(monkeypatch, source)

    first = persist_historical_model_routes(
        run_dir,
        mapping_path=MAPPING_PATH,
        sector_registry_path=REGISTRY_PATH,
    )
    route_artifact = next(
        artifact
        for artifact in first.artifacts
        if artifact.name == "cvm_historical_model_route"
    )
    route_path = run_dir / route_artifact.path
    persisted_bytes = route_path.read_bytes()

    # Simulate process death after route publication and before manifest commit.
    (run_dir / "manifest.json").write_bytes(original_manifest)

    second = persist_historical_model_routes(
        run_dir,
        mapping_path=MAPPING_PATH,
        sector_registry_path=REGISTRY_PATH,
    )

    assert route_path.read_bytes() == persisted_bytes
    assert second.counts["historical_model_routes"] == 1
    assert len(
        [
            artifact
            for artifact in second.artifacts
            if artifact.name == "cvm_historical_model_route"
        ]
    ) == 1
    assert len(source.calls) == 2


def test_persistence_rejects_conflicting_orphan_route_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_dir, original_manifest = _build_run(tmp_path)
    source = FakeRouteSource()
    _patch_materializer(monkeypatch, source)

    first = persist_historical_model_routes(
        run_dir,
        mapping_path=MAPPING_PATH,
        sector_registry_path=REGISTRY_PATH,
    )
    route_artifact = next(
        artifact
        for artifact in first.artifacts
        if artifact.name == "cvm_historical_model_route"
    )
    route_path = run_dir / route_artifact.path

    (run_dir / "manifest.json").write_bytes(original_manifest)
    route_path.write_bytes(b"conflicting-orphan")

    with pytest.raises(FileExistsError, match="different content"):
        persist_historical_model_routes(
            run_dir,
            mapping_path=MAPPING_PATH,
            sector_registry_path=REGISTRY_PATH,
        )


def test_predictable_staging_symlink_is_never_followed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_dir, _original_manifest = _build_run(tmp_path)
    source = FakeRouteSource()
    _patch_materializer(monkeypatch, source)

    outside = tmp_path / "outside.txt"
    outside.write_bytes(b"sentinel")
    predictable = (
        run_dir
        / "normalized/cvm/historical_model_routes_2025.jsonl.gz.tmp"
    )
    predictable.symlink_to(outside)

    updated = persist_historical_model_routes(
        run_dir,
        mapping_path=MAPPING_PATH,
        sector_registry_path=REGISTRY_PATH,
    )

    assert updated.counts["historical_model_routes"] == 1
    assert outside.read_bytes() == b"sentinel"
    assert predictable.is_symlink()


def test_final_output_symlink_is_rejected_without_touching_target(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_dir, original_manifest = _build_run(tmp_path)
    source = FakeRouteSource()
    _patch_materializer(monkeypatch, source)

    outside = tmp_path / "outside.txt"
    outside.write_bytes(b"sentinel")
    final_path = (
        run_dir
        / "normalized/cvm/historical_model_routes_2025.jsonl.gz"
    )
    final_path.symlink_to(outside)

    with pytest.raises(ValueError, match="must not be a symlink"):
        persist_historical_model_routes(
            run_dir,
            mapping_path=MAPPING_PATH,
            sector_registry_path=REGISTRY_PATH,
        )

    assert outside.read_bytes() == b"sentinel"
    assert (run_dir / "manifest.json").read_bytes() == original_manifest


def test_registry_is_parsed_from_the_exact_bytes_that_passed_hash_verification(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_dir, _original_manifest = _build_run(tmp_path)
    source = FakeRouteSource()
    _patch_materializer(monkeypatch, source)

    registry_copy = tmp_path / "sector_registry_v0.6.yml"
    registry_copy.write_bytes(REGISTRY_PATH.read_bytes())
    original_from_bytes = FCAHistoricalModelRouteSource.from_bytes

    def _from_bytes(
        cls: type[FCAHistoricalModelRouteSource],
        *,
        mapping_bytes: bytes,
        mapping_source_document: str,
        sector_registry_bytes: bytes,
        sector_registry_base_dir: str | Path,
    ) -> FCAHistoricalModelRouteSource:
        del cls
        registry_copy.write_bytes(b"version: '0.6.3'\nmodels: []\n")
        return original_from_bytes(
            mapping_bytes=mapping_bytes,
            mapping_source_document=mapping_source_document,
            sector_registry_bytes=sector_registry_bytes,
            sector_registry_base_dir=sector_registry_base_dir,
        )

    monkeypatch.setattr(
        FCAHistoricalModelRouteSource,
        "from_bytes",
        classmethod(_from_bytes),
    )

    updated = persist_historical_model_routes(
        run_dir,
        mapping_path=MAPPING_PATH,
        sector_registry_path=registry_copy,
    )

    assert updated.counts["historical_model_routes"] == 1
    assert registry_copy.read_bytes() != REGISTRY_PATH.read_bytes()


def test_manifest_symlink_is_rejected_before_any_materialization(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_dir, original_manifest = _build_run(tmp_path)
    source = FakeRouteSource()
    _patch_materializer(monkeypatch, source)

    manifest_path = run_dir / "manifest.json"
    real_manifest = tmp_path / "real-manifest.json"
    real_manifest.write_bytes(original_manifest)
    manifest_path.unlink()
    manifest_path.symlink_to(real_manifest)

    with pytest.raises(ValueError, match="bootstrap manifest must not be a symlink"):
        persist_historical_model_routes(
            run_dir,
            mapping_path=MAPPING_PATH,
            sector_registry_path=REGISTRY_PATH,
        )

    assert source.calls == []
    assert real_manifest.read_bytes() == original_manifest


def _patch_materializer(
    monkeypatch: pytest.MonkeyPatch,
    source: FakeRouteSource,
) -> None:
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

    monkeypatch.setattr(
        FCAHistoricalModelRouteSource,
        "materialize_archive",
        _materialize,
    )


def _build_run(tmp_path: Path) -> tuple[Path, bytes]:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    year = 2025

    raw_path = run_dir / "raw/cvm/fca_cia_aberta_2025.zip"
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    raw_path.write_bytes(b"PK-original-fca")

    security = SecurityRecord(
        company_id="cvm:4170",
        ticker="VALE3",
        reference_date=date(year, 12, 31),
        collected_at=COLLECTED_AT,
    )
    security_path = run_dir / "normalized/cvm/securities_2025.jsonl.gz"
    security_path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(
        security_path,
        "wt",
        encoding="utf-8",
        newline="\n",
    ) as file:
        file.write(
            json.dumps(
                security.model_dump(mode="json"),
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        file.write("\n")

    artifacts = [
        _artifact(
            run_dir,
            raw_path,
            name="cvm_fca_raw",
            source="CVM_FCA",
            year=year,
            raw=True,
            rows=None,
        ),
        _artifact(
            run_dir,
            security_path,
            name="cvm_security_master",
            source="CVM_FCA",
            year=year,
            raw=False,
            rows=1,
        ),
    ]
    manifest = PublicDataBootstrapManifest(
        run_id="recovery-test",
        status="COMPLETE",
        started_at=COLLECTED_AT,
        completed_at=COLLECTED_AT,
        start_year=year,
        end_year=year,
        requested_tickers=["VALE3"],
        statements=["DRE"],
        artifacts=artifacts,
    )
    manifest_path = run_dir / "manifest.json"
    manifest_path.write_text(
        manifest.model_dump_json(indent=2),
        encoding="utf-8",
        newline="\n",
    )
    return run_dir, manifest_path.read_bytes()


def _artifact(
    run_dir: Path,
    path: Path,
    *,
    name: str,
    source: str,
    year: int,
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
        reference_year=year,
        raw=raw,
    )