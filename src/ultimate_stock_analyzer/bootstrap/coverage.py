from __future__ import annotations

import gzip
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path
from statistics import mean
from typing import Literal

from pydantic import BaseModel, Field

from ultimate_stock_analyzer.bootstrap.dataset import BootstrapDataset
from ultimate_stock_analyzer.domain.master import (
    FinancialStatementLine,
    IssuerRecord,
    SecurityRecord,
)
from ultimate_stock_analyzer.fundamentals.contracts import (
    GENERAL_CORPORATE_CONTRACT,
    evaluate_contract,
)
from ultimate_stock_analyzer.fundamentals.cvm_accounts import extract_fixed_accounts


class FundamentalCoverageRecord(BaseModel):
    company_id: str
    cvm_code: int
    company_name: str
    tickers: list[str]
    reference_date: date
    fiscal_year: int
    contract: str = GENERAL_CORPORATE_CONTRACT.name
    applicability: Literal["UNRESOLVED_SECTOR_CLASSIFICATION"] = (
        "UNRESOLVED_SECTOR_CLASSIFICATION"
    )
    extracted_accounts: int = Field(ge=0)
    critical_coverage: float = Field(ge=0.0, le=1.0)
    total_coverage: float = Field(ge=0.0, le=1.0)
    point_in_time_critical_coverage: float = Field(ge=0.0, le=1.0)
    missing_critical: list[str]
    missing_supporting: list[str]
    untimed_critical: list[str]
    source_documents: list[str]
    latest_available_from: datetime | None = None
    has_prior_fiscal_year: bool = False
    longitudinal_pair_ready: bool = False


class FundamentalCoverageSummary(BaseModel):
    schema_version: str = "1.0"
    bootstrap_run_id: str
    bootstrap_manifest_sha256: str
    generated_at: datetime
    contract: str = GENERAL_CORPORATE_CONTRACT.name
    applicability: Literal["UNRESOLVED_SECTOR_CLASSIFICATION"] = (
        "UNRESOLVED_SECTOR_CLASSIFICATION"
    )
    companies: int = Field(ge=0)
    company_years: int = Field(ge=0)
    mapped_tickers: int = Field(ge=0)
    critical_complete_company_years: int = Field(ge=0)
    point_in_time_critical_complete_company_years: int = Field(ge=0)
    longitudinal_pair_ready_company_years: int = Field(ge=0)
    mean_critical_coverage: float = Field(ge=0.0, le=1.0)
    mean_total_coverage: float = Field(ge=0.0, le=1.0)
    coverage_buckets: dict[str, int]
    warnings: list[str]


class FundamentalCoverageProfiler:
    """Measure evidence readiness without producing an investment score."""

    def __init__(self, dataset: BootstrapDataset) -> None:
        self.dataset = dataset

    def analyze(self, *, generated_at: datetime) -> tuple[list[FundamentalCoverageRecord], FundamentalCoverageSummary]:
        issuers = {issuer.company_id: issuer for issuer in self.dataset.issuers()}
        securities = self.dataset.securities()
        statements = self.dataset.statements()

        by_period: dict[tuple[str, date], list[FinancialStatementLine]] = defaultdict(list)
        for line in statements:
            if line.fiscal_order != "ÚLTIMO":
                continue
            by_period[(line.company_id, line.reference_date)].append(line)

        records: list[FundamentalCoverageRecord] = []
        for (company_id, reference_date), lines in sorted(by_period.items()):
            issuer = issuers.get(company_id)
            if issuer is None:
                issuer = _issuer_from_line(lines[0])
            extraction = extract_fixed_accounts(
                lines,
                company_id=company_id,
                reference_date=reference_date,
                consolidation_scope=None,
            )
            coverage = evaluate_contract(extraction.values)
            critical_names = set(GENERAL_CORPORATE_CONTRACT.critical_inputs)
            untimed_critical = sorted(
                name
                for name in critical_names
                if name in extraction.lines
                and extraction.lines[name].available_from is None
            )
            timed_critical = sum(
                1
                for name in critical_names
                if name in extraction.lines
                and extraction.lines[name].available_from is not None
            )
            point_in_time_coverage = (
                timed_critical / len(critical_names) if critical_names else 1.0
            )
            available_times = [
                line.available_from
                for line in extraction.lines.values()
                if line.available_from is not None
            ]
            source_documents = sorted(
                {
                    line.source_document
                    for line in extraction.lines.values()
                    if line.source_document
                }
            )
            records.append(
                FundamentalCoverageRecord(
                    company_id=company_id,
                    cvm_code=issuer.cvm_code,
                    company_name=issuer.legal_name,
                    tickers=_tickers_for_period(securities, company_id, reference_date),
                    reference_date=reference_date,
                    fiscal_year=reference_date.year,
                    extracted_accounts=len(extraction.values),
                    critical_coverage=coverage.critical_coverage,
                    total_coverage=coverage.total_coverage,
                    point_in_time_critical_coverage=point_in_time_coverage,
                    missing_critical=list(coverage.missing_critical),
                    missing_supporting=list(coverage.missing_supporting),
                    untimed_critical=untimed_critical,
                    source_documents=source_documents,
                    latest_available_from=max(available_times) if available_times else None,
                )
            )

        _mark_longitudinal_pairs(records)
        summary = _summary(records, self.dataset, generated_at)
        return records, summary

    def write(
        self,
        output_root: str | Path,
        *,
        generated_at: datetime,
    ) -> FundamentalCoverageSummary:
        records, summary = self.analyze(generated_at=generated_at)
        output_dir = Path(output_root) / "coverage" / self.dataset.manifest.run_id
        if output_dir.exists():
            raise FileExistsError(f"coverage output already exists: {output_dir}")
        output_dir.mkdir(parents=True)
        with gzip.open(
            output_dir / "fundamental_coverage.jsonl.gz",
            "wt",
            encoding="utf-8",
            newline="\n",
        ) as file:
            for record in records:
                file.write(record.model_dump_json())
                file.write("\n")
        (output_dir / "summary.json").write_text(
            summary.model_dump_json(indent=2),
            encoding="utf-8",
            newline="\n",
        )
        return summary


def _issuer_from_line(line: FinancialStatementLine) -> IssuerRecord:
    return IssuerRecord(
        company_id=line.company_id,
        cvm_code=line.cvm_code,
        cnpj=line.cnpj,
        legal_name=line.company_name,
        collected_at=line.collected_at,
        source=line.source,
    )


def _tickers_for_period(
    securities: list[SecurityRecord],
    company_id: str,
    reference_date: date,
) -> list[str]:
    candidates = [
        security
        for security in securities
        if security.company_id == company_id
        and (security.trading_start is None or security.trading_start <= reference_date)
        and (security.trading_end is None or security.trading_end >= reference_date)
    ]
    if not candidates:
        candidates = [security for security in securities if security.company_id == company_id]
    return sorted({security.ticker.upper() for security in candidates})


def _mark_longitudinal_pairs(records: list[FundamentalCoverageRecord]) -> None:
    by_company_year = {(record.company_id, record.fiscal_year): record for record in records}
    for record in records:
        prior = by_company_year.get((record.company_id, record.fiscal_year - 1))
        record.has_prior_fiscal_year = prior is not None
        record.longitudinal_pair_ready = (
            prior is not None
            and record.point_in_time_critical_coverage == 1.0
            and prior.point_in_time_critical_coverage == 1.0
        )


def _summary(
    records: list[FundamentalCoverageRecord],
    dataset: BootstrapDataset,
    generated_at: datetime,
) -> FundamentalCoverageSummary:
    critical_complete = sum(record.critical_coverage == 1.0 for record in records)
    point_in_time_complete = sum(
        record.point_in_time_critical_coverage == 1.0 for record in records
    )
    longitudinal = sum(record.longitudinal_pair_ready for record in records)
    buckets = {
        "critical_100pct": critical_complete,
        "critical_90_to_99pct": sum(
            0.9 <= record.critical_coverage < 1.0 for record in records
        ),
        "critical_75_to_89pct": sum(
            0.75 <= record.critical_coverage < 0.9 for record in records
        ),
        "critical_below_75pct": sum(record.critical_coverage < 0.75 for record in records),
    }
    return FundamentalCoverageSummary(
        bootstrap_run_id=dataset.manifest.run_id,
        bootstrap_manifest_sha256=dataset.manifest_sha256,
        generated_at=generated_at,
        companies=len({record.company_id for record in records}),
        company_years=len(records),
        mapped_tickers=len({ticker for record in records for ticker in record.tickers}),
        critical_complete_company_years=critical_complete,
        point_in_time_critical_complete_company_years=point_in_time_complete,
        longitudinal_pair_ready_company_years=longitudinal,
        mean_critical_coverage=mean(record.critical_coverage for record in records) if records else 0.0,
        mean_total_coverage=mean(record.total_coverage for record in records) if records else 0.0,
        coverage_buckets=buckets,
        warnings=[
            "Coverage is measured against the general-corporate accounting contract only.",
            "Sector applicability is unresolved until sector/subsector/segment data is materialized.",
            "Coverage readiness is not an investment score or recommendation.",
        ],
    )
