from __future__ import annotations

import gzip
import hashlib
from pathlib import Path

from pydantic import BaseModel

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


class BootstrapDataset:
    """Verified reader for one completed public-data bootstrap run."""

    def __init__(self, run_dir: str | Path, *, verify: bool = True) -> None:
        self.run_dir = Path(run_dir)
        manifest_path = self.run_dir / "manifest.json"
        if not manifest_path.is_file():
            raise FileNotFoundError(f"bootstrap manifest not found: {manifest_path}")
        self.manifest_path = manifest_path
        self.manifest = PublicDataBootstrapManifest.model_validate_json(
            manifest_path.read_text(encoding="utf-8")
        )
        if self.manifest.status != "COMPLETE":
            raise ValueError(
                f"bootstrap run {self.manifest.run_id} is not COMPLETE: "
                f"{self.manifest.status}"
            )
        if verify:
            self.verify_artifacts()

    @property
    def manifest_sha256(self) -> str:
        return hashlib.sha256(self.manifest_path.read_bytes()).hexdigest()

    def verify_artifacts(self) -> None:
        for artifact in self.manifest.artifacts:
            path = self.run_dir / artifact.path
            if not path.is_file():
                raise FileNotFoundError(f"bootstrap artifact missing: {path}")
            content = path.read_bytes()
            if len(content) != artifact.bytes:
                raise ValueError(f"bootstrap artifact size mismatch: {artifact.path}")
            digest = hashlib.sha256(content).hexdigest()
            if digest != artifact.sha256:
                raise ValueError(f"bootstrap artifact checksum mismatch: {artifact.path}")

    def issuers(self) -> list[IssuerRecord]:
        artifact = self._one("cvm_issuer_master")
        return self._read_models(artifact, IssuerRecord)

    def securities(self) -> list[SecurityRecord]:
        rows: list[SecurityRecord] = []
        for artifact in self._many("cvm_security_master"):
            rows.extend(self._read_models(artifact, SecurityRecord))
        return rows

    def statements(self) -> list[FinancialStatementLine]:
        rows: list[FinancialStatementLine] = []
        for artifact in self._many("cvm_financial_statements"):
            rows.extend(self._read_models(artifact, FinancialStatementLine))
        return rows

    def sector_classifications(self) -> list[SectorClassificationRecord]:
        rows: list[SectorClassificationRecord] = []
        for artifact in self._many("b3_sector_classification"):
            rows.extend(self._read_models(artifact, SectorClassificationRecord))
        by_company: dict[str, SectorClassificationRecord] = {}
        for row in rows:
            existing = by_company.get(row.company_id)
            if existing is not None and existing != row:
                raise ValueError(
                    "bootstrap contains conflicting sector classifications for "
                    f"{row.company_id}"
                )
            by_company[row.company_id] = row
        return list(by_company.values())

    def _one(self, name: str) -> BootstrapArtifact:
        artifacts = self._many(name)
        if len(artifacts) != 1:
            raise ValueError(f"expected one bootstrap artifact named {name}, found {len(artifacts)}")
        return artifacts[0]

    def _many(self, name: str) -> list[BootstrapArtifact]:
        artifacts = [artifact for artifact in self.manifest.artifacts if artifact.name == name]
        return sorted(
            artifacts,
            key=lambda item: (item.reference_year is None, item.reference_year or -1, item.path),
        )

    def _read_models[T: BaseModel](
        self,
        artifact: BootstrapArtifact,
        model: type[T],
    ) -> list[T]:
        path = self.run_dir / artifact.path
        rows: list[T] = []
        with gzip.open(path, "rt", encoding="utf-8") as file:
            for line_number, line in enumerate(file, start=1):
                payload = line.strip()
                if not payload:
                    continue
                try:
                    rows.append(model.model_validate_json(payload))
                except Exception as exc:
                    raise ValueError(
                        f"invalid {model.__name__} at {artifact.path}:{line_number}"
                    ) from exc
        if artifact.rows is not None and len(rows) != artifact.rows:
            raise ValueError(
                f"bootstrap normalized row-count mismatch for {artifact.path}: "
                f"manifest={artifact.rows} actual={len(rows)}"
            )
        return rows
