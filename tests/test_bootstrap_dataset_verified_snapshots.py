from __future__ import annotations

import gzip
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from ultimate_stock_analyzer.backtesting.historical_model_routes import HistoricalModelRoute
from ultimate_stock_analyzer.bootstrap.dataset import BootstrapDataset
from ultimate_stock_analyzer.bootstrap.public_data import (
    BootstrapArtifact,
    PublicDataBootstrapManifest,
)


def test_historical_route_reader_reverifies_exact_bytes_before_parsing(
    tmp_path: Path,
) -> None:
    run_dir, route_path = _route_run(tmp_path)
    dataset = BootstrapDataset(run_dir)

    replacement = HistoricalModelRoute(
        company_id="cvm:1",
        fiscal_year=2025,
        model_id="banks",
        available_from=datetime(2026, 3, 1, tzinfo=UTC),
        evidence_source="CVM_FCA",
        source_document="replacement",
        evidence_sha256="b" * 64,
        mapping_rule_version="replacement",
        point_in_time_eligible=True,
    )
    _write_routes(route_path, [replacement])

    with pytest.raises(ValueError, match="checksum mismatch"):
        dataset.historical_model_routes()


def test_historical_route_reader_rejects_symlink_swap_after_dataset_init(
    tmp_path: Path,
) -> None:
    run_dir, route_path = _route_run(tmp_path)
    dataset = BootstrapDataset(run_dir)

    outside = tmp_path / "outside.jsonl.gz"
    outside.write_bytes(route_path.read_bytes())
    route_path.unlink()
    route_path.symlink_to(outside)

    with pytest.raises(ValueError, match="must not be a symlink"):
        dataset.historical_model_routes()


def _route_run(tmp_path: Path) -> tuple[Path, Path]:
    run_dir = tmp_path / "run"
    route_path = run_dir / "normalized/cvm/historical_model_routes_2025.jsonl.gz"
    route_path.parent.mkdir(parents=True)

    route = HistoricalModelRoute(
        company_id="cvm:1",
        fiscal_year=2025,
        model_id="commodities",
        available_from=datetime(2026, 3, 1, tzinfo=UTC),
        evidence_source="CVM_FCA",
        source_document="source",
        evidence_sha256="a" * 64,
        mapping_rule_version="test",
        point_in_time_eligible=True,
    )
    _write_routes(route_path, [route])
    content = route_path.read_bytes()
    artifact = BootstrapArtifact(
        name="cvm_historical_model_route",
        source="CVM_FCA",
        path=route_path.relative_to(run_dir).as_posix(),
        sha256=hashlib.sha256(content).hexdigest(),
        bytes=len(content),
        rows=1,
        reference_year=2025,
        raw=False,
    )
    now = datetime(2026, 9, 4, tzinfo=UTC)
    manifest = PublicDataBootstrapManifest(
        run_id="route-reader-test",
        status="COMPLETE",
        started_at=now,
        completed_at=now,
        start_year=2025,
        end_year=2025,
        requested_tickers=["TEST3"],
        statements=["DRE"],
        artifacts=[artifact],
    )
    (run_dir / "manifest.json").write_text(
        manifest.model_dump_json(indent=2),
        encoding="utf-8",
        newline="\n",
    )
    return run_dir, route_path


def _write_routes(path: Path, routes: list[HistoricalModelRoute]) -> None:
    with gzip.open(path, "wt", encoding="utf-8", newline="\n") as file:
        for route in routes:
            file.write(
                json.dumps(
                    route.model_dump(mode="json"),
                    ensure_ascii=False,
                    sort_keys=True,
                )
            )
            file.write("\n")
