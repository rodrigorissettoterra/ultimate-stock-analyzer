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


def _ifdata_report_rows(
    dataset: BootstrapDataset,
    *,
    year: int,
    report_number: int,
    cod_inst: str,
) -> list[dict[str, Any]]:
    report_path = (
        dataset.run_dir
        / "raw"
        / "bcb"
        / "ifdata"
        / str(year)
        / f"{year}12_report_{report_number}.json"
    )
    if not report_path.is_file():
        raise RuntimeError(f"IFData raw report unavailable: {report_path.name}")

    payload = json.loads(report_path.read_bytes())
    rows = payload.get("value") if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        raise RuntimeError(
            f"IFData report {report_number} must contain a value list"
        )

    selected: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        if str(row.get("CodInst") or "").strip() != cod_inst:
            continue
        selected.append(
            {
                field: row.get(field)
                for field in (
                    "Conta",
                    "Grupo",
                    "NomeColuna",
                    "DescricaoColuna",
                    "Saldo",
                )
            }
        )
    return sorted(selected, key=lambda row: str(row.get("Conta") or ""))


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


def _itub_bank_profile(
    dataset: BootstrapDataset,
    routes: dict[str, dict[str, Any]],
    *,
    year: int,
) -> dict[str, Any] | None:
    if "ITUB4" not in routes:
        return None
    company_id = str(routes["ITUB4"]["company_id"])
    profiles = [
        row
        for row in dataset.bank_profiles()
        if row.company_id == company_id and row.fiscal_year == year
    ]
    if len(profiles) != 1:
        raise RuntimeError(
            f"expected one IFData bank profile for ITUB4/{year}, found {len(profiles)}"
        )
    profile = profiles[0]
    if profile.source_scope != "PRUDENTIAL_CONGLOMERATE":
        raise RuntimeError(
            f"ITUB4 IFData source scope is not prudential: {profile.source_scope}"
        )
    if profile.institution_type != 1:
        raise RuntimeError(
            f"ITUB4 IFData institution type is not prudential: {profile.institution_type}"
        )
    if profile.point_in_time_eligible:
        raise RuntimeError(
            "latest-state IFData bank profile must not be point-in-time eligible"
        )

    required_metrics = {
        "roe": profile.roe,
        "roa": profile.roa,
        "cost_of_credit": profile.cost_of_credit,
        "basel_ratio": profile.basel_ratio,
        "tier1_ratio": profile.tier1_ratio,
        "equity_to_assets": profile.equity_to_assets,
    }
    missing = sorted(name for name, value in required_metrics.items() if value is None)
    if missing:
        diagnostic_fields = {
            "total_assets": profile.total_assets,
            "prior_total_assets": profile.prior_total_assets,
            "equity": profile.equity,
            "prior_equity": profile.prior_equity,
            "gross_credit_portfolio": profile.gross_credit_portfolio,
            "prior_gross_credit_portfolio": profile.prior_gross_credit_portfolio,
            "annual_net_income": profile.annual_net_income,
            "annual_credit_loss_result": profile.annual_credit_loss_result,
        }
        raise RuntimeError(
            "ITUB4 IFData profile is missing verified bank metrics: "
            + ", ".join(missing)
            + "; evidence="
            + json.dumps(diagnostic_fields, sort_keys=True, default=str)
        )
    return {
        "company_id": profile.company_id,
        "fiscal_year": profile.fiscal_year,
        "ifdata_cod_inst": profile.ifdata_cod_inst,
        "ifdata_name": profile.ifdata_name,
        "source_scope": profile.source_scope,
        "institution_type": profile.institution_type,
        "available_from_estimate": profile.available_from_estimate,
        "point_in_time_eligible": profile.point_in_time_eligible,
        "report_4_discovery_rows": _ifdata_report_rows(
            dataset,
            year=year,
            report_number=4,
            cod_inst=profile.ifdata_cod_inst,
        ),
        **required_metrics,
    }


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
        "schema_version": "1.2",
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
                include_bank_ifdata=True,
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
        bank_profile = _itub_bank_profile(dataset, routes, year=year)

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
        if "ITUB4" in requested and manifest.counts.get("bank_prudential_profiles", 0) <= 0:
            raise RuntimeError("bootstrap returned no BCB IFData bank profile")
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
        if "ITUB4" in requested and coverage.bank_contract_available_company_years < 1:
            raise RuntimeError(
                "coverage profiler did not activate the bank IFData accounting contract"
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
                "bank_profile": bank_profile,
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
                    "bank_contract_available_company_years": (
                        coverage.bank_contract_available_company_years
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
        description="Run a bounded real-data smoke test against official CVM/B3/BCB sources."
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
