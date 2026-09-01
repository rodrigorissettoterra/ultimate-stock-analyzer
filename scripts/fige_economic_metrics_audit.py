from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from ultimate_stock_analyzer.collectors.cvm import CVMCollector
from ultimate_stock_analyzer.collectors.cvm_targeted_statements import (
    load_company_statements_from_archive,
)
from ultimate_stock_analyzer.fundamentals.fige_economic_metrics_audit import (
    audit_fige_economic_history,
    audit_fige_economic_year,
)
from ultimate_stock_analyzer.fundamentals.fige_financial_contract import (
    FIGE_COMPANY_ID,
    evaluate_fige_financial_contract,
)
from ultimate_stock_analyzer.scoring.statement_tree_audit import (
    audit_financial_statement_tree,
)

FIGE_CVM_CODE = 6041
ESSENTIAL_DIAGNOSTIC_METRICS = (
    "roe_closing_equity",
    "roa_closing_assets",
    "net_income_to_closing_financial_assets",
    "financial_assets_to_assets",
    "securities_to_assets",
    "equity_to_assets",
    "financial_liabilities_to_assets",
    "fiscal_liabilities_to_assets",
    "gross_intermediation_result_to_closing_assets",
    "intermediation_expense_to_revenue",
    "pretax_income_to_gross_intermediation_result",
    "effective_tax_burden",
    "net_income_to_pretax_income",
    "non_continuing_result_gap_to_abs_net_income",
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Audit FIGE economic metrics using its validated CVM accounting contract."
    )
    parser.add_argument("--start-year", type=int, default=2021)
    parser.add_argument("--end-year", type=int, default=2025)
    parser.add_argument(
        "--output",
        default="fige-economic-metrics-audit.json",
    )
    args = parser.parse_args()

    if args.start_year > args.end_year:
        raise ValueError("start-year must not be greater than end-year")

    collected_at = datetime.now(UTC)
    collector = CVMCollector()
    annual_audits = []
    contract_coverage_by_year: list[dict[str, object]] = []
    incomplete_years: list[int] = []
    prior_values: dict[str, float] | None = None

    for year in range(args.start_year, args.end_year + 1):
        archive = collector.download_zip("DFP", year)
        lines = load_company_statements_from_archive(
            archive,
            cvm_code=FIGE_CVM_CODE,
            document_type="DFP",
            statements=("BPA", "BPP", "DRE"),
            scope_token="ind",
            collected_at=collected_at,
            collector=collector,
        )
        report = audit_financial_statement_tree(
            lines,
            company_id=FIGE_COMPANY_ID,
            max_depth=4,
        )
        if report.reference_date is None or not report.lines:
            raise RuntimeError(f"no FIGE DFP evidence for fiscal year {year}")

        evaluation = evaluate_fige_financial_contract(report)
        coverage = evaluation.coverage
        complete = (
            coverage.critical_coverage == 1.0
            and coverage.total_coverage == 1.0
        )
        contract_coverage_by_year.append(
            {
                "fiscal_year": year,
                "reference_date": report.reference_date,
                "critical_coverage": coverage.critical_coverage,
                "total_coverage": coverage.total_coverage,
                "missing_critical": coverage.missing_critical,
                "missing_supporting": coverage.missing_supporting,
            }
        )
        if not complete:
            raise RuntimeError(
                f"FIGE accounting contract incomplete for fiscal year {year}"
            )

        annual = audit_fige_economic_year(
            company_id=FIGE_COMPANY_ID,
            fiscal_year=year,
            reference_date=report.reference_date,
            values=evaluation.values,
            prior_year_values=prior_values,
        )
        missing_metrics = tuple(
            metric_id
            for metric_id in ESSENTIAL_DIAGNOSTIC_METRICS
            if annual.metrics.get(metric_id) is None
        )
        if missing_metrics:
            incomplete_years.append(year)

        annual_audits.append(annual)
        prior_values = evaluation.values

    history = audit_fige_economic_history(annual_audits)
    payload = {
        "generated_at": collected_at.isoformat(),
        "source": "CVM_DFP_CIA_ABERTA",
        "company_id": FIGE_COMPANY_ID,
        "start_year": args.start_year,
        "end_year": args.end_year,
        "effect": "diagnostic_only_not_routed_or_scored",
        "point_in_time_eligible": False,
        "accounting_contract": "fige_financial_cvm_v1",
        "accounting_contract_coverage_by_year": contract_coverage_by_year,
        "economic_audit": history.to_dict(),
        "essential_metric_incomplete_years": incomplete_years,
        "notes": [
            (
                "All ratios are derived only from FIGE values that first passed the exact "
                "statement/account/label accounting contract."
            ),
            (
                "Average-balance profitability ratios use only the immediately preceding "
                "audited fiscal year; 2021 remains UNKNOWN for those variants."
            ),
            (
                "The known extraordinary 2022 distribution prevents raw equity/assets "
                "growth from being interpreted as economic quality."
            ),
            (
                "Dividend sustainability remains blocked until a FIGE-specific "
                "distribution/DMPL contract exists."
            ),
            (
                "This artifact is diagnostic evidence only. It does not change model "
                "routing, weights, thresholds, rankings or backtests."
            ),
            (
                "Latest-state CVM annual archives are not strict publication/revision-history "
                "PIT evidence for historical backtesting."
            ),
        ],
    }
    Path(args.output).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, default=str)
        + "\n",
        encoding="utf-8",
    )

    if incomplete_years:
        raise RuntimeError(
            "FIGE economic audit has unavailable essential metrics for years: "
            + ", ".join(str(year) for year in incomplete_years)
        )


if __name__ == "__main__":
    main()
