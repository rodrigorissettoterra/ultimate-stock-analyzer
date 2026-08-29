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
    summary: dict[str, Any] = {
        "schema_version": "1.0",
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

        coverage = FundamentalCoverageProfiler(dataset).write(
            data_dir,
            generated_at=datetime.now(UTC),
        )
        if manifest.status != "COMPLETE":
            raise RuntimeError(f"bootstrap status is {manifest.status}")
        if manifest.counts.get("issuers", 0) <= 0:
            raise RuntimeError("bootstrap returned no issuers")
        if manifest.counts.get("securities", 0) <= 0:
            raise RuntimeError("bootstrap returned no securities")
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

        summary.update(
            {
                "status": "PASS",
                "completed_at": datetime.now(UTC).isoformat(),
                "source_policy": manifest.source_policy,
                "bootstrap_counts": manifest.counts,
                "security_tickers_found": sorted(security_tickers),
                "price_tickers_found": sorted(price_tickers),
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
