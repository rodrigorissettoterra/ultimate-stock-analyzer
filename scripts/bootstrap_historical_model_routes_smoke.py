from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import tempfile
from datetime import UTC, date, datetime
from pathlib import Path

from ultimate_stock_analyzer.bootstrap.dataset import BootstrapDataset
from ultimate_stock_analyzer.bootstrap.historical_model_routes import (
    FCAHistoricalModelRouteSource,
    persist_historical_model_routes,
)
from ultimate_stock_analyzer.bootstrap.public_data import (
    BootstrapArtifact,
    PublicDataBootstrapManifest,
)
from ultimate_stock_analyzer.collectors.cvm import CVMCollector
from ultimate_stock_analyzer.domain.master import SecurityRecord

YEAR = 2025
COMPANIES = (
    ("cvm:4170", "VALE3"),
    ("cvm:9512", "PETR4"),
    ("cvm:19348", "ITUB4"),
)
EXPECTED = {
    "cvm:4170": ("commodities", "2025-04-12T00:00:00+00:00"),
    "cvm:9512": ("commodities", "2025-05-16T00:00:00+00:00"),
    "cvm:19348": ("banks", "2025-03-12T00:00:00+00:00"),
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    collected_at = datetime.now(UTC)
    collector = CVMCollector(timeout_seconds=90.0)
    archive = collector.download_zip("FCA", YEAR)

    with tempfile.TemporaryDirectory(prefix="usa-fca-route-bootstrap-") as temp_dir:
        run_dir = Path(temp_dir)
        raw_path = run_dir / f"raw/cvm/fca_cia_aberta_{YEAR}.zip"
        raw_path.parent.mkdir(parents=True, exist_ok=True)
        raw_path.write_bytes(archive)

        security_path = run_dir / f"normalized/cvm/securities_{YEAR}.jsonl.gz"
        security_path.parent.mkdir(parents=True, exist_ok=True)
        rows = [
            SecurityRecord(
                company_id=company_id,
                ticker=ticker,
                reference_date=date(YEAR, 12, 31),
                collected_at=collected_at,
            )
            for company_id, ticker in COMPANIES
        ]
        with gzip.open(security_path, "wt", encoding="utf-8", newline="\n") as file:
            for row in rows:
                file.write(
                    json.dumps(
                        row.model_dump(mode="json"),
                        ensure_ascii=False,
                        sort_keys=True,
                    )
                )
                file.write("\n")

        manifest = PublicDataBootstrapManifest(
            run_id="live-fca-historical-route-persistence",
            status="COMPLETE",
            started_at=collected_at,
            completed_at=collected_at,
            start_year=YEAR,
            end_year=YEAR,
            requested_tickers=[ticker for _company_id, ticker in COMPANIES],
            statements=["DRE"],
            artifacts=[
                _artifact(
                    run_dir,
                    raw_path,
                    name="cvm_fca_raw",
                    source="CVM_FCA",
                    reference_year=YEAR,
                    raw=True,
                    rows=None,
                ),
                _artifact(
                    run_dir,
                    security_path,
                    name="cvm_security_master",
                    source="CVM_FCA",
                    reference_year=YEAR,
                    raw=False,
                    rows=len(rows),
                ),
            ],
        )
        (run_dir / "manifest.json").write_text(
            manifest.model_dump_json(indent=2),
            encoding="utf-8",
            newline="\n",
        )

        source = FCAHistoricalModelRouteSource.from_paths(
            mapping_path="config/backtesting/fca_model_routes_v0.2.yml",
            sector_registry_path="config/scoring/sector_registry_v0.6.yml",
        )
        updated = persist_historical_model_routes(run_dir, route_source=source)
        dataset = BootstrapDataset(run_dir)
        routes = dataset.historical_model_routes()

        observed = {
            route.company_id: (route.model_id, route.available_from.isoformat())
            for route in routes
        }
        if observed != EXPECTED:
            raise SystemExit(f"unexpected persisted routes: {observed}")
        if updated.counts.get("historical_model_routes") != 3:
            raise SystemExit("unexpected historical route count")
        if any(not route.point_in_time_eligible for route in routes):
            raise SystemExit("persisted route lost PIT eligibility")

        route_artifact = next(
            artifact
            for artifact in updated.artifacts
            if artifact.name == "cvm_historical_model_route"
        )
        evidence = {
            "schema_version": "0.1",
            "year": YEAR,
            "fca_downloads_performed_by_smoke": 1,
            "fca_archive_sha256": hashlib.sha256(archive).hexdigest(),
            "persisted_route_artifact_sha256": route_artifact.sha256,
            "manifest_sha256": dataset.manifest_sha256,
            "route_count": len(routes),
            "routes": [route.model_dump(mode="json") for route in routes],
            "current_b3_fallback_used": False,
            "effect": "manifest_bound_fca_reused_for_historical_model_routes",
        }

    args.output.write_text(
        json.dumps(evidence, indent=2, ensure_ascii=False, sort_keys=True),
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps(evidence, indent=2, ensure_ascii=False, sort_keys=True))


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


if __name__ == "__main__":
    main()
