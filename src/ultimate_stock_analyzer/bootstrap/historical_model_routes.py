from __future__ import annotations

import gzip
import hashlib
import json
import os
import re
import stat
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

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
_TRUSTED_MAPPING_SHA256 = "2160ff0f9302aeb96992d19ba9bbd8483d429d2a4405a7450999d13ed3129c46"
_TRUSTED_REGISTRY_SHA256 = "51b54271624084bcff9bccd73178ab43f284811fbf5edcd35a305e03c1f1f171"
_TRUSTED_MAPPING_RULE_VERSION = "fca-sector-activity-v0.2"
_TRUSTED_SECTOR_REGISTRY_VERSION = "0.6.3"


@dataclass(frozen=True, slots=True)
class FCAHistoricalModelRouteSource:
    mapping: FCAHistoricalModelRouteMapping
    sector_registry: SectorModelRegistry

    @classmethod
    def from_bytes(
        cls,
        *,
        mapping_bytes: bytes,
        mapping_source_document: str,
        sector_registry_bytes: bytes,
        sector_registry_base_dir: str | Path,
    ) -> FCAHistoricalModelRouteSource:
        return cls(
            mapping=FCAHistoricalModelRouteMapping.from_yaml_bytes(
                mapping_bytes,
                source_document=mapping_source_document,
            ),
            sector_registry=SectorModelRegistry.from_yaml_bytes(
                sector_registry_bytes,
                base_dir=sector_registry_base_dir,
            ),
        )

    @classmethod
    def from_paths(
        cls,
        *,
        mapping_path: str | Path,
        sector_registry_path: str | Path,
    ) -> FCAHistoricalModelRouteSource:
        mapping_file = Path(mapping_path)
        registry_file = Path(sector_registry_path)
        return cls.from_bytes(
            mapping_bytes=mapping_file.read_bytes(),
            mapping_source_document=mapping_file.as_posix(),
            sector_registry_bytes=registry_file.read_bytes(),
            sector_registry_base_dir=registry_file.parent,
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


@dataclass(frozen=True, slots=True)
class _VerifiedArtifactSnapshot:
    artifact: BootstrapArtifact
    path: Path
    content: bytes


@dataclass(frozen=True, slots=True)
class _StagedRouteArtifact:
    content: bytes
    temp_path: Path | None
    final_path: Path
    artifact: BootstrapArtifact
    preexisting: bool


def persist_historical_model_routes(
    run_dir: str | Path,
    *,
    mapping_path: str | Path,
    sector_registry_path: str | Path,
) -> PublicDataBootstrapManifest:
    """Persist routes from manifest-bound FCA bytes using only trusted routing config."""
    resolved_run_dir = Path(run_dir).resolve(strict=True)
    if not resolved_run_dir.is_dir():
        raise NotADirectoryError(f"bootstrap run directory is not a directory: {resolved_run_dir}")

    manifest_path = resolved_run_dir / "manifest.json"
    original_manifest_bytes = _read_regular_file_no_follow(
        manifest_path,
        label="bootstrap manifest",
    )
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

    route_source = _trusted_fca_route_source(
        mapping_path=mapping_path,
        sector_registry_path=sector_registry_path,
    )

    planned: list[tuple[int, tuple[HistoricalModelRoute, ...]]] = []
    verified_inputs: list[_VerifiedArtifactSnapshot] = []
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

        raw_snapshot = _verified_artifact_snapshot(resolved_run_dir, raw_artifact)
        security_snapshot = _verified_artifact_snapshot(
            resolved_run_dir,
            security_artifact,
        )
        verified_inputs.extend((raw_snapshot, security_snapshot))

        securities = _read_security_records(
            security_snapshot.content,
            security_artifact,
        )
        requested_tickers = set(manifest.requested_tickers)
        if any(item.ticker.upper() not in requested_tickers for item in securities):
            raise ValueError(
                f"FCA security artifact {year} contains tickers outside the "
                "bootstrap filter"
            )

        company_ids = tuple(sorted({item.company_id for item in securities}))
        if not company_ids:
            planned.append((year, ()))
            continue
        requested_cvm_codes = tuple(_cvm_code(company_id) for company_id in company_ids)
        source_url = CVMCollector().dataset_url("FCA", year)

        materialization = route_source.materialize_archive(
            raw_snapshot.content,
            collected_at=manifest.started_at,
            delivery_year=year,
            source_url=source_url,
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
        _validate_fca_route_provenance(
            route_source=route_source,
            materialization=materialization,
            routes=routes,
            source_url=source_url,
            year=year,
        )
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

    staged: list[_StagedRouteArtifact] = []
    total_routes = 0
    try:
        for year, routes in planned:
            output_dir = _ensure_contained_directory(
                resolved_run_dir,
                Path("normalized") / "cvm",
            )
            final_path = output_dir / f"historical_model_routes_{year}.jsonl.gz"
            content = _route_file_bytes(routes)
            existing = _existing_regular_file_bytes(final_path)
            preexisting = existing is not None
            if preexisting and existing != content:
                raise FileExistsError(
                    "historical model-route output already exists with "
                    f"different content: {final_path}"
                )
            temp_path = (
                None
                if preexisting
                else _write_exclusive_temp_bytes(
                    resolved_run_dir,
                    output_dir,
                    prefix=f".{final_path.name}.",
                    suffix=".tmp",
                    content=content,
                )
            )
            artifact = _artifact_from_content(
                resolved_run_dir,
                final_path=final_path,
                content=content,
                name="cvm_historical_model_route",
                source="CVM_FCA",
                reference_year=year,
                rows=len(routes),
            )
            staged.append(
                _StagedRouteArtifact(
                    content=content,
                    temp_path=temp_path,
                    final_path=final_path,
                    artifact=artifact,
                    preexisting=preexisting,
                )
            )
            total_routes += len(routes)

        counts = dict(manifest.counts)
        counts["historical_model_routes"] = total_routes
        warning = (
            "Historical model routes are bounded to the requested tickers and use "
            "exact CVM FCA filing evidence with the repository-approved routing "
            "mapping/registry and no current-B3 fallback."
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
                    *(
                        item.artifact.model_dump(mode="python")
                        for item in staged
                    ),
                ],
                "counts": counts,
                "warnings": warnings,
            }
        )
        updated_bytes = updated.model_dump_json(indent=2).encode("utf-8")

        created_final_paths: list[Path] = []
        manifest_temp: Path | None = None
        try:
            for item in staged:
                if not item.preexisting:
                    if item.temp_path is None:
                        raise RuntimeError("missing route staging path")
                    os.replace(item.temp_path, item.final_path)
                    created_final_paths.append(item.final_path)
                published = _read_regular_file_no_follow(
                    item.final_path,
                    label="historical model-route output",
                )
                if published != item.content:
                    raise ValueError(
                        "historical model-route publication content changed before "
                        f"manifest commit: {item.final_path}"
                    )

            _revalidate_verified_inputs(verified_inputs)
            current_manifest = _read_regular_file_no_follow(
                manifest_path,
                label="bootstrap manifest",
            )
            if current_manifest != original_manifest_bytes:
                raise ValueError(
                    "bootstrap manifest changed concurrently before historical "
                    "model-route commit"
                )

            manifest_temp = _write_exclusive_temp_bytes(
                resolved_run_dir,
                resolved_run_dir,
                prefix=".manifest.json.",
                suffix=".tmp",
                content=updated_bytes,
            )
            os.replace(manifest_temp, manifest_path)
            manifest_temp = None
        except Exception:
            if manifest_temp is not None:
                _unlink_regular_file_if_present(manifest_temp)
            for path in created_final_paths:
                _unlink_regular_file_if_present(path)
            raise
        return updated
    finally:
        for item in staged:
            if item.temp_path is not None:
                _unlink_regular_file_if_present(item.temp_path)


def _trusted_fca_route_source(
    *,
    mapping_path: str | Path,
    sector_registry_path: str | Path,
) -> FCAHistoricalModelRouteSource:
    mapping_file = Path(mapping_path)
    registry_file = Path(sector_registry_path)
    mapping_bytes = _read_regular_file_no_follow(
        mapping_file,
        label="FCA model-route mapping",
    )
    registry_bytes = _read_regular_file_no_follow(
        registry_file,
        label="sector registry",
    )
    mapping_sha256 = hashlib.sha256(mapping_bytes).hexdigest()
    registry_sha256 = hashlib.sha256(registry_bytes).hexdigest()
    if mapping_sha256 != _TRUSTED_MAPPING_SHA256:
        raise ValueError(
            "untrusted FCA model-route mapping content: "
            f"expected={_TRUSTED_MAPPING_SHA256} actual={mapping_sha256}"
        )
    if registry_sha256 != _TRUSTED_REGISTRY_SHA256:
        raise ValueError(
            "untrusted sector registry content for historical routing: "
            f"expected={_TRUSTED_REGISTRY_SHA256} actual={registry_sha256}"
        )

    source = FCAHistoricalModelRouteSource.from_bytes(
        mapping_bytes=mapping_bytes,
        mapping_source_document=mapping_file.as_posix(),
        sector_registry_bytes=registry_bytes,
        sector_registry_base_dir=registry_file.parent,
    )
    if source.mapping.mapping_rule_version != _TRUSTED_MAPPING_RULE_VERSION:
        raise ValueError(
            "trusted FCA mapping rule version mismatch: "
            f"expected={_TRUSTED_MAPPING_RULE_VERSION} "
            f"actual={source.mapping.mapping_rule_version}"
        )
    if source.mapping.source_sha256 != _TRUSTED_MAPPING_SHA256:
        raise ValueError("trusted FCA mapping SHA-256 changed during load")
    if source.sector_registry.version != _TRUSTED_SECTOR_REGISTRY_VERSION:
        raise ValueError(
            "trusted sector registry version mismatch: "
            f"expected={_TRUSTED_SECTOR_REGISTRY_VERSION} "
            f"actual={source.sector_registry.version}"
        )
    source.mapping.validate_against_registry(source.sector_registry)
    return source


def _validate_fca_route_provenance(
    *,
    route_source: FCAHistoricalModelRouteSource,
    materialization: FCAHistoricalModelRouteMaterialization,
    routes: tuple[HistoricalModelRoute, ...],
    source_url: str,
    year: int,
) -> None:
    if materialization.route_count != len(routes):
        raise ValueError(
            f"historical model-route materialization count mismatch for {year}: "
            f"declared={materialization.route_count} actual={len(routes)}"
        )
    if materialization.mapping_rule_version != route_source.mapping.mapping_rule_version:
        raise ValueError(f"historical model-route mapping version mismatch for {year}")
    if materialization.mapping_source_sha256 != route_source.mapping.source_sha256:
        raise ValueError(f"historical model-route mapping SHA-256 mismatch for {year}")
    if materialization.sector_registry_version != route_source.sector_registry.version:
        raise ValueError(f"historical model-route registry version mismatch for {year}")

    expected_mapping_version = (
        f"{route_source.mapping.mapping_rule_version}+sector-registry/"
        f"{route_source.sector_registry.version}"
    )
    document_prefix = f"{source_url}#ID_Documento="
    for route in routes:
        if route.evidence_source != "CVM_FCA":
            raise ValueError(
                f"historical model-route provenance mismatch for {year}: "
                f"{route.company_id} evidence_source={route.evidence_source!r}"
            )
        if not route.source_document.startswith(document_prefix) or ":Versao=" not in (
            route.source_document
        ):
            raise ValueError(
                "historical model-route source document is not bound to the "
                f"official FCA archive for {year}: {route.company_id}"
            )
        if route.mapping_rule_version != expected_mapping_version:
            raise ValueError(
                f"historical model-route mapping provenance mismatch for {year}: "
                f"{route.company_id} route={route.mapping_rule_version!r} "
                f"trusted={expected_mapping_version!r}"
            )


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


def _verified_artifact_snapshot(
    run_dir: Path,
    artifact: BootstrapArtifact,
) -> _VerifiedArtifactSnapshot:
    path = _contained_artifact_path(run_dir, artifact.path)
    content = _read_regular_file_no_follow(
        path,
        label=f"bootstrap artifact {artifact.path}",
    )
    if len(content) != artifact.bytes:
        raise ValueError(f"bootstrap artifact size mismatch: {artifact.path}")
    if hashlib.sha256(content).hexdigest() != artifact.sha256:
        raise ValueError(f"bootstrap artifact checksum mismatch: {artifact.path}")
    return _VerifiedArtifactSnapshot(
        artifact=artifact,
        path=path,
        content=content,
    )


def _verified_artifact_bytes(
    run_dir: Path,
    artifact: BootstrapArtifact,
) -> bytes:
    """Compatibility helper retained for focused tests and callers."""
    return _verified_artifact_snapshot(run_dir, artifact).content


def _revalidate_verified_inputs(
    snapshots: list[_VerifiedArtifactSnapshot],
) -> None:
    for snapshot in snapshots:
        current = _read_regular_file_no_follow(
            snapshot.path,
            label=f"bootstrap artifact {snapshot.artifact.path}",
        )
        if current != snapshot.content:
            raise ValueError(
                "bootstrap artifact changed after verification and before historical "
                f"model-route commit: {snapshot.artifact.path}"
            )


def _contained_artifact_path(run_dir: Path, artifact_path: str) -> Path:
    relative = Path(artifact_path)
    if relative.is_absolute():
        raise ValueError(f"bootstrap artifact path must be relative: {artifact_path}")
    candidate = Path(os.path.abspath(run_dir / relative))
    try:
        candidate.relative_to(run_dir)
    except ValueError as exc:
        raise ValueError(
            f"bootstrap artifact escapes run directory: {artifact_path}"
        ) from exc
    _assert_no_symlink_components(run_dir, candidate.parent)
    return candidate


def _ensure_contained_directory(run_dir: Path, relative: Path) -> Path:
    if relative.is_absolute():
        raise ValueError(f"bootstrap output directory must be relative: {relative}")
    candidate = Path(os.path.abspath(run_dir / relative))
    try:
        candidate.relative_to(run_dir)
    except ValueError as exc:
        raise ValueError(
            f"bootstrap output directory escapes run directory: {relative}"
        ) from exc

    current = run_dir
    for part in candidate.relative_to(run_dir).parts:
        current = current / part
        try:
            info = current.lstat()
        except FileNotFoundError:
            current.mkdir()
            info = current.lstat()
        if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode):
            raise ValueError(
                f"bootstrap output directory contains unsafe path component: {current}"
            )
    return candidate


def _assert_no_symlink_components(root: Path, directory: Path) -> None:
    try:
        relative = directory.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"path escapes bootstrap run directory: {directory}") from exc

    current = root
    for part in relative.parts:
        current = current / part
        info = current.lstat()
        if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode):
            raise ValueError(f"unsafe bootstrap path component: {current}")


def _read_regular_file_no_follow(path: Path, *, label: str) -> bytes:
    try:
        before = path.lstat()
    except FileNotFoundError as exc:
        raise FileNotFoundError(f"{label} not found: {path}") from exc
    if stat.S_ISLNK(before.st_mode):
        raise ValueError(f"{label} must not be a symlink: {path}")
    if not stat.S_ISREG(before.st_mode):
        raise ValueError(f"{label} must be a regular file: {path}")

    flags = os.O_RDONLY
    if hasattr(os, "O_BINARY"):
        flags |= os.O_BINARY
    flags |= getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(path, flags)
    except OSError as exc:
        raise ValueError(f"unable to open {label} without following symlinks: {path}") from exc
    try:
        after = os.fstat(fd)
        if not stat.S_ISREG(after.st_mode):
            raise ValueError(f"{label} must remain a regular file: {path}")
        if (
            before.st_dev != after.st_dev
            or before.st_ino != after.st_ino
        ):
            raise ValueError(f"{label} changed while being opened: {path}")
        chunks: list[bytes] = []
        while True:
            chunk = os.read(fd, 1024 * 1024)
            if not chunk:
                break
            chunks.append(chunk)
        return b"".join(chunks)
    finally:
        os.close(fd)


def _existing_regular_file_bytes(path: Path) -> bytes | None:
    try:
        path.lstat()
    except FileNotFoundError:
        return None
    return _read_regular_file_no_follow(
        path,
        label="historical model-route output",
    )


def _write_exclusive_temp_bytes(
    root: Path,
    directory: Path,
    *,
    prefix: str,
    suffix: str,
    content: bytes,
) -> Path:
    fd, raw_path = tempfile.mkstemp(
        prefix=prefix,
        suffix=suffix,
        dir=directory,
    )
    path = Path(raw_path)
    try:
        resolved_path = path.resolve(strict=True)
        try:
            resolved_path.relative_to(root)
        except ValueError as exc:
            raise ValueError(
                f"staging path escaped bootstrap run directory: {path}"
            ) from exc
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode):
            raise ValueError(f"staging path is not a regular file: {path}")
        with os.fdopen(fd, "wb", closefd=True) as file:
            fd = -1
            file.write(content)
            file.flush()
            os.fsync(file.fileno())
        return path
    except Exception:
        if fd >= 0:
            os.close(fd)
        _unlink_regular_file_if_present(path)
        raise


def _unlink_regular_file_if_present(path: Path) -> None:
    try:
        info = path.lstat()
    except FileNotFoundError:
        return
    if stat.S_ISLNK(info.st_mode):
        path.unlink(missing_ok=True)
        return
    if not stat.S_ISREG(info.st_mode):
        raise ValueError(f"refusing to unlink non-regular path: {path}")
    path.unlink(missing_ok=True)


def _read_security_records(
    content: bytes,
    artifact: BootstrapArtifact,
) -> list[SecurityRecord]:
    try:
        text = gzip.decompress(content).decode("utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise ValueError(
            f"invalid gzip/UTF-8 security artifact: {artifact.path}"
        ) from exc

    rows: list[SecurityRecord] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
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


def _route_file_bytes(
    routes: tuple[HistoricalModelRoute, ...],
) -> bytes:
    lines = [
        json.dumps(
            route.model_dump(mode="json"),
            ensure_ascii=False,
            sort_keys=True,
        )
        for route in routes
    ]
    payload = ("\n".join(lines) + ("\n" if lines else "")).encode("utf-8")
    return gzip.compress(payload, mtime=0)


def _artifact_from_content(
    run_dir: Path,
    *,
    final_path: Path,
    content: bytes,
    name: str,
    source: str,
    reference_year: int,
    rows: int,
) -> BootstrapArtifact:
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