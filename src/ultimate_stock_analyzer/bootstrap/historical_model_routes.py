from __future__ import annotations

import gzip
import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Protocol

from ultimate_stock_analyzer.backtesting.cvm_fca_applicability_filing_ledger import (
    build_fca_applicability_filing_ledger,
)
from ultimate_stock_analyzer.backtesting.cvm_fca_historical_model_routes import (
    FCAHistoricalModelRouteMapping,
    FCAHistoricalModelRouteMaterialization,
    materialize_fca_historical_model_routes,
)
from ultimate_stock_analyzer.backtesting.historical_model_routes import (
    HistoricalModelRoute,
)
from ultimate_stock_analyzer.bootstrap.public_data import (
    BootstrapArtifact,
    PublicDataBootstrapManifest,
)
from ultimate_stock_analyzer.collectors.cvm import CVMCollector
from ultimate_stock_analyzer.domain.master import SecurityRecord
from ultimate_stock_analyzer.scoring.sector_models import SectorModelRegistry

_CANONICAL_COMPANY_ID = re.compile(r"^cvm:([1-9][0-9]*)$")


@dataclass(frozen=True, slots=True)
class FCAHistoricalModelRouteSource:
    mapping: FCAHistoricalModelRouteMapping
    sector_registry: SectorModelRegistry

    @classmethod
    def from_paths(
        cls,
        *,
        mapping_path: str | Path,
        sector_registry_path: str | Path,
    ) -> "FCAHistoricalModelRouteSource":
        return cls(
            mapping=FCAHistoricalModelRouteMapping.from_yaml(mapping_path),
            sector_registry=SectorModelRegistry.from_yaml(sector_registry_path),
        )

    def materialize_archive(
        self,
        archive_content: bytes,
        *,
        collected_at: datetime,
        delivery_year: int,
        source_url: str,
        requested_cvm_codes: tuple[int, ...],
    ) -> FCAHistoricalModelRouteMaterialization:
        ledger = build_fca_applicability_filing_ledger(
            archive_content=archive_content,
            collected_at=collected_at,
            delivery_year=delivery_year,
            source_url=source_url,
            requested_cvm_codes=requested_cvm_codes,
        )
        return materialize_fca_historical_model_routes(
            ledgers=[ledger],
            mapping=self.mapping,
            sector_registry=self.sector_registry,
        )


class HistoricalModelRouteSource(Protocol):
    def materialize_archive(
        self,
        archive_content: bytes,
        *,
        collected_at: datetime,
        delivery_year: int,
        source_url: str,
        requested_cvm_codes: tuple[int, ...],
    ) -> FCAHistoricalModelRouteMaterialization: ...


def persist_historical_model_routes(
    run_dir: str | Path,
    *,
    route_source: HistoricalModelRouteSource,
) -> PublicDataBootstrapManifest:
    resolved_run_dir = Path(run_dir)
    manifest_path = resolved_run_dir / "manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(f"bootstrap manifest not found: {manifest_path}")

    original_manifest_bytes = manifest_path.read_bytes()
    manifest = PublicDataBootstrapManifest.model_validate_json(original_manifest_bytes)
    if manifest.status != "COMPLETE":
        raise ValueError(
            f"bootstrap run {manifest.run_id} is not COMPLETE: {manifest.status}"
        )
    if not manifest.requested_tickers:
        raise ValueError(
            "historical model-route persistence is currently bounded to "
            "bootstrap runs with an explicit ticker filter"
        )
    if any(
        artifact.name == "cvm_historical_model_route"
        for artifact in manifest.artifacts
    ):
        raise ValueError("bootstrap already contains historical model-route artifacts")

    planned: list[tuple[int, tuple[HistoricalModelRoute, ...]]] = []
    for year in range(manifest.start_year, manifest.end_year + 1):
        raw_artifact = _one_artifact(
            manifest,
            name="cvm_fca_raw",
            reference_year=year,
        )
        security_artifact = _one_artifact(
            manifest,
            name="cvm_security_master",
            reference_year=year,
        )
        if not raw_artifact.raw or raw_artifact.source != "CVM_FCA":
            raise ValueError(f"invalid FCA raw artifact contract for {year}")
        if security_artifact.raw or security_artifact.source != "CVM_FCA":
            raise ValueError(f"invalid FCA security artifact contract for {year}")

        raw_path = _verified_artifact_path(resolved_run_dir, raw_artifact)
        security_path = _verified_artifact_path(resolved_run_dir, security_artifact)
        securities = _read_security_records(security_path, security_artifact)
        requested_tickers = set(manifest.requested_tickers)
        if any(item.ticker.upper() not in requested_tickers for item in securities):
            raise ValueError(
                f"FCA security artifact {year} contains tickers outside the "
                "bootstrap filter"
            )

        company_ids = tuple(sorted({item.company_id for item in securities}))
        if not company_ids:
            raise ValueError(
                f"FCA security artifact {year} contains no selected companies"
            )
        requested_cvm_codes = tuple(_cvm_code(company_id) for company_id in company_ids)

        materialization = route_source.materialize_archive(
            raw_path.read_bytes(),
            collected_at=manifest.started_at,
            delivery_year=year,
            source_url=CVMCollector().dataset_url("FCA", year),
            requested_cvm_codes=requested_cvm_codes,
        )
        if materialization.blockers:
            raise ValueError(
                f"historical model-route materialization blocked for {year}: "
                + ", ".join(materialization.blockers)
            )
        if materialization.blocked_company_years:
            raise ValueError(
                f"historical model-route company-years blocked for {year}: "
                + ", ".join(materialization.blocked_company_years)
            )

        routes = tuple(materialization.routes)
        expected_keys = {(company_id, year) for company_id in company_ids}
        observed_keys = {route.key for route in routes}
        if observed_keys != expected_keys or len(routes) != len(expected_keys):
            raise ValueError(
                f"historical model-route coverage mismatch for {year}: "
                f"expected={sorted(expected_keys)} observed={sorted(observed_keys)}"
            )
        if any(not route.point_in_time_eligible for route in routes):
            raise ValueError(f"historical model-route lost PIT eligibility for {year}")
        planned.append((year, routes))

    staged: list[tuple[Path, Path, BootstrapArtifact]] = []
    total_routes = 0
    try:
        for year, routes in planned:
            final_path = (
                resolved_run_dir
                / "normalized"
                / "cvm"
                / f"historical_model_routes_{year}.jsonl.gz"
            )
            if final_path.exists():
                raise FileExistsError(
                    f"historical model-route output already exists: {final_path}"
                )
            final_path.parent.mkdir(parents=True, exist_ok=True)
            temp_path = final_path.with_name(final_path.name + ".tmp")
            _write_routes(temp_path, routes)
            artifact = _artifact_from_file(
                resolved_run_dir,
                final_path=final_path,
                content_path=temp_path,
                name="cvm_historical_model_route",
                source="CVM_FCA",
                reference_year=year,
                rows=len(routes),
            )
            staged.append((temp_path, final_path, artifact))
            total_routes += len(routes)

        counts = dict(manifest.counts)
        counts["historical_model_routes"] = total_routes
        warning = (
            "Historical model routes are bounded to the requested tickers and use "
            "exact CVM FCA filing evidence with no current-B3 fallback."
        )
        warnings = list(manifest.warnings)
        if warning not in warnings:
            warnings.append(warning)
        updated = PublicDataBootstrapManifest.model_validate(
            {
                **manifest.model_dump(mode="python"),
                "artifacts": [
                    *(
                        artifact.model_dump(mode="python")
                        for artifact in manifest.artifacts
                    ),
                    *(artifact.model_dump(mode="python") for _, _, artifact in staged),
                ],
                "counts": counts,
                "warnings": warnings,
            }
        )
        updated_text = updated.model_dump_json(indent=2)

        created_final_paths: list[Path] = []
        manifest_temp = manifest_path.with_name(manifest_path.name + ".tmp")
        try:
            for temp_path, final_path, _artifact in staged:
                temp_path.replace(final_path)
                created_final_paths.append(final_path)
            manifest_temp.write_text(
                updated_text,
                encoding="utf-8",
                newline="\n",
            )
            manifest_temp.replace(manifest_path)
        except Exception:
            manifest_temp.unlink(missing_ok=True)
            for path in created_final_paths:
                path.unlink(missing_ok=True)
            if manifest_path.read_bytes() != original_manifest_bytes:
                manifest_path.write_bytes(original_manifest_bytes)
            raise
        return updated
    finally:
        for temp_path, _final_path, _artifact in staged:
            temp_path.unlink(missing_ok=True)


def _one_artifact(
    manifest: PublicDataBootstrapManifest,
    *,
    name: str,
    reference_year: int,
) -> BootstrapArtifact:
    matches = [
        artifact
        for artifact in manifest.artifacts
        if artifact.name == name and artifact.reference_year == reference_year
    ]
    if len(matches) != 1:
        raise ValueError(
            f"expected one {name} artifact for {reference_year}, found {len(matches)}"
        )
    return matches[0]


def _verified_artifact_path(
    run_dir: Path,
    artifact: BootstrapArtifact,
) -> Path:
    path = run_dir / artifact.path
    if not path.is_file():
        raise FileNotFoundError(f"bootstrap artifact missing: {path}")
    content = path.read_bytes()
    if len(content) != artifact.bytes:
        raise ValueError(f"bootstrap artifact size mismatch: {artifact.path}")
    if hashlib.sha256(content).hexdigest() != artifact.sha256:
        raise ValueError(f"bootstrap artifact checksum mismatch: {artifact.path}")
    return path


def _read_security_records(
    path: Path,
    artifact: BootstrapArtifact,
) -> list[SecurityRecord]:
    rows: list[SecurityRecord] = []
    with gzip.open(path, "rt", encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            payload = line.strip()
            if not payload:
                continue
            try:
                rows.append(SecurityRecord.model_validate_json(payload))
            except Exception as exc:
                raise ValueError(
                    f"invalid SecurityRecord at {artifact.path}:{line_number}"
                ) from exc
    if artifact.rows is not None and len(rows) != artifact.rows:
        raise ValueError(
            f"bootstrap normalized row-count mismatch for {artifact.path}: "
            f"manifest={artifact.rows} actual={len(rows)}"
        )
    return rows


def _cvm_code(company_id: str) -> int:
    match = _CANONICAL_COMPANY_ID.fullmatch(company_id)
    if match is None:
        raise ValueError(
            "historical model-route bootstrap identity must be exact cvm:<CD_CVM>"
        )
    return int(match.group(1))


def _write_routes(
    path: Path,
    routes: tuple[HistoricalModelRoute, ...],
) -> None:
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


def _artifact_from_file(
    run_dir: Path,
    *,
    final_path: Path,
    content_path: Path,
    name: str,
    source: str,
    reference_year: int,
    rows: int,
) -> BootstrapArtifact:
    content = content_path.read_bytes()
    return BootstrapArtifact(
        name=name,
        source=source,
        path=final_path.relative_to(run_dir).as_posix(),
        sha256=hashlib.sha256(content).hexdigest(),
        bytes=len(content),
        rows=rows,
        reference_year=reference_year,
        raw=False,
    )
