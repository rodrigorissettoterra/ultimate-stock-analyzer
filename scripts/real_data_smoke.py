from __future__ import annotations

import argparse
import gzip
import json
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ultimate_stock_analyzer.bootstrap import (
    BootstrapDataset,
    FundamentalCoverageProfiler,
    PublicDataBootstrapPlan,
    PublicDataBootstrapService,
)
from ultimate_stock_analyzer.scoring.sector_models import SectorModelRegistry

EXPECTED_SMOKE_MODELS = {
    "PETR4": "commodities",
    "VALE3": "commodities",
    "ITUB4": "banks",
}


def _price_tickers(dataset: BootstrapDataset) -> set[str]:
    tickers: set[str] = set()
    for artifact in dataset.manifest.artifacts:
        if artifact.name != "b3_cotahist":
            continue
        path = dataset.run_dir / artifact.path
        with gzip.open(path, "rt", encoding="utf-8") as file:
            for line in file:
                payload = line.strip()
                if not payload:
                    continue
                row = json.loads(payload)
                ticker = str(row.get("ticker") or "").strip().upper()
                if ticker:
                    tickers.add(ticker)
    return tickers


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False, default=str) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _copy_if_exists(source: Path, destination: Path) -> None:
    if source.is_file():
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)


def _sector_routes(
    dataset: BootstrapDataset,
    requested: set[str],
    registry: SectorModelRegistry,
) -> dict[str, dict[str, Any]]:
    classifications = {row.company_id: row for row in dataset.sector_classifications()}
    if not classifications:
        raise RuntimeError("bootstrap returned no current B3 sector classifications")
    if any(row.point_in_time_eligible for row in classifications.values()):
        raise RuntimeError("current B3 sector snapshot must not be point-in-time eligible")

    companies_by_ticker: dict[str, set[str]] = {}
    for security in dataset.securities():
        ticker = security.ticker.upper()
        if ticker in requested:
            companies_by_ticker.setdefault(ticker, set()).add(security.company_id)

    routes: dict[str, dict[str, Any]] = {}
    for ticker in sorted(requested):
        company_ids = companies_by_ticker.get(ticker, set())
        if len(company_ids) != 1:
            raise RuntimeError(
                f"expected one CVM company for {ticker}, found {sorted(company_ids)}"
            )
        company_id = next(iter(company_ids))
        classification = classifications.get(company_id)
        if classification is None:
            raise RuntimeError(
                f"current B3 sector classification missing for {ticker} ({company_id})"
            )
        selection = registry.select(
            {
                "sector": classification.sector,
                "subsector": classification.subsector,
                "segment": classification.segment,
            }
        )
        routes[ticker] = {
            "company_id": company_id,
            "issuer_code": classification.issuer_code,
            "sector": classification.sector,
            "subsector": classification.subsector,
            "segment": classification.segment,
            "listing_segment": classification.listing_segment,
            "model_id": selection.model_id,
            "selection_reason": selection.reason,
            "is_fallback": selection.is_fallback,
            "point_in_time_eligible": classification.point_in_time_eligible,
        }

    for ticker, expected_model in EXPECTED_SMOKE_MODELS.items():
        if ticker not in requested:
            continue
        route = routes[ticker]
        if route["model_id"] != expected_model:
            raise RuntimeError(
                f"unexpected sector model for {ticker}: "
                f"expected={expected_model} actual={route['model_id']}"
            )
        if route["is_fallback"]:
            raise RuntimeError(f"benchmark ticker {ticker} used default sector fallback")
    return routes


def run_smoke(
    *,
    year: int,
    tickers: tuple[str, ...],
    data_dir: Path,
    output_dir: Path,
) -> dict[str, Any]:
    started_at = datetime.now(UTC)
    run_id = f"smoke-{year}-{started_at:%Y%m%dT%H%M%SZ}"
    run_dir = data_dir / "bootstrap" / run_id
    requested = {ticker.strip().upper() for ticker in tickers if ticker.strip()}
    repo_root = Path(__file__).resolve().parents[1]
    registry = SectorModelRegistry.from_yaml(
        repo_root / "config/scoring/sector_registry_v0.6.yml"
    )
    summary: dict[str, Any] = {
        "schema_version": "1.1",
        "status": "FAILED",
        "year": year,
        "tickers": sorted(requested),
        "bootstrap_run_id": run_id,
        "started_at": started_at.isoformat(),
    }

    try:
        manifest = PublicDataBootstrapService(data_dir).run(
            PublicDataBootstrapPlan(
                start_year=year,
                end_year=year,
                tickers=tuple(sorted(requested)),
                include_current_sector_classification=True,
            ),
            collected_at=started_at,
            run_id=run_id,
        )
        dataset = BootstrapDataset(run_dir)
        securities = dataset.securities()
        security_tickers = {row.ticker.upper() for row in securities}
        price_tickers = _price_tickers(dataset)
        missing_security_tickers = sorted(requested - security_tickers)
        missing_price_tickers = sorted(requested - price_tickers)
        routes = _sector_routes(dataset, requested, registry)

        coverage = FundamentalCoverageProfiler(
            dataset,
            sector_registry=registry,
        ).write(
            data_dir,
            generated_at=datetime.now(UTC),
        )
        if manifest.status != "COMPLETE":
            raise RuntimeError(f"bootstrap status is {manifest.status}")
        if manifest.counts.get("issuers", 0) <= 0:
            raise RuntimeError("bootstrap returned no issuers")
        if manifest.counts.get("securities", 0) <= 0:
            raise RuntimeError("bootstrap returned no securities")
        if manifest.counts.get("sector_classifications", 0) <= 0:
            raise RuntimeError("bootstrap returned no sector classifications")
        if manifest.counts.get("financial_statement_lines", 0) <= 0:
            raise RuntimeError("bootstrap returned no financial statement lines")
        if manifest.counts.get("price_bars", 0) <= 0:
            raise RuntimeError("bootstrap returned no B3 price bars")
        if missing_security_tickers:
            raise RuntimeError(
                "requested tickers missing from normalized FCA security master: "
                + ", ".join(missing_security_tickers)
            )
        if missing_price_tickers:
            raise RuntimeError(
                "requested tickers missing from normalized B3 COTAHIST: "
                + ", ".join(missing_price_tickers)
            )
        if coverage.resolved_sector_model_company_years != coverage.company_years:
            raise RuntimeError(
                "coverage profiler did not resolve a sector model for every company-year"
            )

        summary.update(
            {
                "status": "PASS",
                "completed_at": datetime.now(UTC).isoformat(),
                "source_policy": manifest.source_policy,
                "bootstrap_counts": manifest.counts,
                "security_tickers_found": sorted(security_tickers),
                "price_tickers_found": sorted(price_tickers),
                "sector_routes": routes,
                "coverage": {
                    "companies": coverage.companies,
                    "company_years": coverage.company_years,
                    "critical_complete_company_years": (
                        coverage.critical_complete_company_years
                    ),
                    "point_in_time_critical_complete_company_years": (
                        coverage.point_in_time_critical_complete_company_years
                    ),
                    "longitudinal_pair_ready_company_years": (
                        coverage.longitudinal_pair_ready_company_years
                    ),
                    "resolved_sector_model_company_years": (
                        coverage.resolved_sector_model_company_years
                    ),
                    "specialized_contract_required_company_years": (
                        coverage.specialized_contract_required_company_years
                    ),
                    "general_corporate_applicable_company_years": (
                        coverage.general_corporate_applicable_company_years
                    ),
                    "sector_model_counts": coverage.sector_model_counts,
                    "mean_critical_coverage": coverage.mean_critical_coverage,
                    "mean_total_coverage": coverage.mean_total_coverage,
                    "coverage_buckets": coverage.coverage_buckets,
                },
                "warnings": [*manifest.warnings, *coverage.warnings],
            }
        )
        return summary
    except Exception as exc:
        summary.update(
            {
                "completed_at": datetime.now(UTC).isoformat(),
                "error": f"{type(exc).__name__}: {exc}",
            }
        )
        raise
    finally:
        output_dir.mkdir(parents=True, exist_ok=True)
        _copy_if_exists(run_dir / "manifest.json", output_dir / "bootstrap_manifest.json")
        coverage_summary = data_dir / "coverage" / run_id / "summary.json"
        _copy_if_exists(coverage_summary, output_dir / "coverage_summary.json")
        _write_json(output_dir / "smoke_summary.json", summary)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run a bounded real-data smoke test against official CVM/B3 sources."
    )
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--ticker", action="append", default=[])
    parser.add_argument("--data-dir", default="./data")
    parser.add_argument("--output-dir", default="./smoke-artifacts")
    args = parser.parse_args()

    tickers = tuple(args.ticker) or ("PETR4", "VALE3", "ITUB4")
    run_smoke(
        year=args.year,
        tickers=tickers,
        data_dir=Path(args.data_dir),
        output_dir=Path(args.output_dir),
    )


if __name__ == "__main__":
    main()
