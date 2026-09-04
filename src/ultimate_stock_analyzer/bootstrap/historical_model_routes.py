from __future__ import annotations

import gzip
import hashlib
import json
import re
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
    def from_paths(
        cls,
        *,
        mapping_path: str | Path,
        sector_registry_path: str | Path,
    ) -> FCAHistoricalModelRouteSource:
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


def persist_historical_model_routes(
    run_dir: str | Path,
    *,
    mapping_path: str | Path,
    sector_registry_path: str | Path,
) -> PublicDataBootstrapManifest:
    """Persist routes from manifest-bound FCA bytes using only trusted routing config."""
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

    route_source = _trusted_fca_route_source(
        mapping_path=mapping_path,
        sector_registry_path=sector_registry_path,
    )

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

        raw_bytes = _verified_artifact_bytes(resolved_run_dir, raw_artifact)
        security_bytes = _verified_artifact_bytes(
            resolved_run_dir,
            security_artifact,
        )
        securities = _read_security_records(security_bytes, security_artifact)
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
            raw_bytes,
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

    staged: list[
        tuple[bytes, Path, Path, BootstrapArtifact, bool]
    ] = []
    total_routes = 0
    try:
        for year, routes in planned:
            final_path = (
                resolved_run_dir
                / "normalized"
                / "cvm"
                / f"historical_model_routes_{year}.jsonl.gz"
            )
            final_path.parent.mkdir(parents=True, exist_ok=True)
            content = _route_file_bytes(routes)
            preexisting = final_path.exists()
            if preexisting:
                existing = final_path.read_bytes()
                if existing != content:
                    raise FileExistsError(
                        "historical model-route output already exists with "
                        f"different content: {final_path}"
                    )
            temp_path = final_path.with_name(final_path.name + ".tmp")
            if not preexisting:
                temp_path.write_bytes(content)
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
                (content, temp_path, final_path, artifact, preexisting)
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
                        artifact.model_dump(mode="python")
                        for _content, _temp, _final, artifact, _preexisting in staged
                    ),
                ],
                "counts": counts,
                "warnings": warnings,
            }
        )
        updated_text = updated.model_dump_json(indent=2)

        created_final_paths: list[Path] = []
        manifest_temp = manifest_path.with_name(manifest_path.name + ".tmp")
        try:
            for content, temp_path, final_path, _artifact, preexisting in staged:
                if not preexisting:
                    temp_path.replace(final_path)
                    created_final_paths.append(final_path)
                if final_path.read_bytes() != content:
                    raise ValueError(
                        "historical model-route publication content changed before "
                        f"manifest commit: {final_path}"
                    )
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
        for _content, temp_path, _final_path, _artifact, _preexisting in staged:
            temp_path.unlink(missing_ok=True)


def _trusted_fca_route_source(
    *,
    mapping_path: str | Path,
    sector_registry_path: str | Path,
) -> FCAHistoricalModelRouteSource:
    mapping_file = Path(mapping_path)
    registry_file = Path(sector_registry_path)
    mapping_sha256 = hashlib.sha256(mapping_file.read_bytes()).hexdigest()
    registry_sha256 = hashlib.sha256(registry_file.read_bytes()).hexdigest()
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

    source = FCAHistoricalModelRouteSource.from_paths(
        mapping_path=mapping_file,
        sector_registry_path=registry_file,
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


def _verified_artifact_bytes(
    run_dir: Path,
    artifact: BootstrapArtifact,
) -> bytes:
    root = run_dir.resolve()
    path = (root / artifact.path).resolve()
    if path != root and root not in path.parents:
        raise ValueError(f"bootstrap artifact escapes run directory: {artifact.path}")
    if not path.is_file():
        raise FileNotFoundError(f"bootstrap artifact missing: {path}")
    content = path.read_bytes()
    if len(content) != artifact.bytes:
        raise ValueError(f"bootstrap artifact size mismatch: {artifact.path}")
    if hashlib.sha256(content).hexdigest() != artifact.sha256:
        raise ValueError(f"bootstrap artifact checksum mismatch: {artifact.path}")
    return content


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