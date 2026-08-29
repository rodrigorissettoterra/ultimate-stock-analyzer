from __future__ import annotations

import gzip
import hashlib
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from ultimate_stock_analyzer.bootstrap.dataset import BootstrapDataset
from ultimate_stock_analyzer.bootstrap.public_data import (
    BootstrapArtifact,
    PublicDataBootstrapManifest,
)
from ultimate_stock_analyzer.domain.master import IssuerRecord


def _write_models(path: Path, rows: list[IssuerRecord]) -> BootstrapArtifact:
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wt", encoding="utf-8") as file:
        for row in rows:
            file.write(row.model_dump_json())
            file.write("\n")
    content = path.read_bytes()
    return BootstrapArtifact(
        name="cvm_issuer_master",
        source="CVM_CAD",
        path=path.name,
        sha256=hashlib.sha256(content).hexdigest(),
        bytes=len(content),
        rows=len(rows),
        raw=False,
    )


def _dataset(tmp_path: Path) -> tuple[Path, BootstrapArtifact]:
    row = IssuerRecord(
        company_id="cvm:1",
        cvm_code=1,
        legal_name="Teste S.A.",
        collected_at=datetime(2025, 3, 1, tzinfo=UTC),
    )
    artifact = _write_models(tmp_path / "issuers.jsonl.gz", [row])
    manifest = PublicDataBootstrapManifest(
        run_id="bootstrap-test",
        status="COMPLETE",
        started_at=datetime(2025, 3, 1, tzinfo=UTC),
        completed_at=datetime(2025, 3, 1, tzinfo=UTC),
        start_year=2024,
        end_year=2024,
        requested_tickers=[],
        statements=["DRE"],
        artifacts=[artifact],
    )
    (tmp_path / "manifest.json").write_text(manifest.model_dump_json(), encoding="utf-8")
    return tmp_path, artifact


def test_dataset_verifies_and_reads_normalized_models(tmp_path: Path) -> None:
    run_dir, _ = _dataset(tmp_path)
    dataset = BootstrapDataset(run_dir)
    assert dataset.manifest.run_id == "bootstrap-test"
    assert dataset.issuers()[0].legal_name == "Teste S.A."
    assert len(dataset.manifest_sha256) == 64


def test_dataset_rejects_checksum_mismatch(tmp_path: Path) -> None:
    run_dir, artifact = _dataset(tmp_path)
    path = run_dir / artifact.path
    path.write_bytes(path.read_bytes() + b"tamper")
    with pytest.raises(ValueError, match="size mismatch"):
        BootstrapDataset(run_dir)


def test_dataset_rejects_failed_manifest(tmp_path: Path) -> None:
    manifest = PublicDataBootstrapManifest(
        run_id="failed",
        status="FAILED",
        started_at=datetime(2025, 1, 1, tzinfo=UTC),
        completed_at=datetime(2025, 1, 1, tzinfo=UTC),
        start_year=2024,
        end_year=2024,
        requested_tickers=[],
        statements=[],
    )
    (tmp_path / "manifest.json").write_text(manifest.model_dump_json(), encoding="utf-8")
    with pytest.raises(ValueError, match="not COMPLETE"):
        BootstrapDataset(tmp_path)
