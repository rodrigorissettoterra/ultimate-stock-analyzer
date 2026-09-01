from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from ultimate_stock_analyzer.orchestration.cvm_ingestion import CVMIngestionService
from ultimate_stock_analyzer.scoring.statement_schema_stability import (
    STATUS_STABLE_EXACT,
    StatementSchemaCandidate,
    audit_statement_schema_stability,
)
from ultimate_stock_analyzer.scoring.statement_tree_audit import (
    audit_financial_statement_tree,
)

FIGE_COMPANY_ID = "cvm:6041"

FIGE_2025_SCHEMA_CANDIDATES = (
    StatementSchemaCandidate(
        "total_assets",
        "BPA",
        "1",
        "Ativo Total",
        tier="core",
    ),
    StatementSchemaCandidate(
        "cash_and_equivalents",
        "BPA",
        "1.01",
        "Caixa e Equivalentes de Caixa",
        tier="core",
    ),
    StatementSchemaCandidate(
        "financial_assets",
        "BPA",
        "1.02",
        "Ativos Financeiros",
        tier="core",
    ),
    StatementSchemaCandidate(
        "securities_amortized_cost",
        "BPA",
        "1.02.04.03",
        "Títulos e Valores Mobiliários",
    ),
    StatementSchemaCandidate(
        "financial_liabilities_amortized_cost",
        "BPP",
        "2.02",
        "Passivos Financeiros ao Custo Amortizado",
    ),
    StatementSchemaCandidate(
        "provisions",
        "BPP",
        "2.03",
        "Provisões",
    ),
    StatementSchemaCandidate(
        "fiscal_liabilities",
        "BPP",
        "2.04",
        "Passivos Fiscais",
    ),
    StatementSchemaCandidate(
        "equity",
        "BPP",
        "2.07",
        "Patrimônio Líquido",
        tier="core",
    ),
    StatementSchemaCandidate(
        "financial_intermediation_revenue",
        "DRE",
        "3.01",
        "Receitas de Intermediação Financeira",
        tier="core",
    ),
    StatementSchemaCandidate(
        "financial_intermediation_expense",
        "DRE",
        "3.02",
        "Despesas de Intermediação Financeira",
        tier="core",
    ),
    StatementSchemaCandidate(
        "gross_financial_intermediation_result",
        "DRE",
        "3.03",
        "Resultado Bruto de Intermediação Financeira",
        tier="core",
    ),
    StatementSchemaCandidate(
        "other_operating_result",
        "DRE",
        "3.04",
        "Outras Despesas e Receitas Operacionais",
    ),
    StatementSchemaCandidate(
        "pretax_income",
        "DRE",
        "3.05",
        "Resultado antes dos Tributos sobre o Lucro",
        tier="core",
    ),
    StatementSchemaCandidate(
        "income_tax",
        "DRE",
        "3.06",
        "Imposto de Renda e Contribuição Social sobre o Lucro",
        tier="core",
    ),
    StatementSchemaCandidate(
        "continuing_operations_income",
        "DRE",
        "3.07",
        "Lucro ou Prejuízo das Operações Continuadas",
    ),
    StatementSchemaCandidate(
        "net_income",
        "DRE",
        "3.11",
        "Lucro ou Prejuízo Líquido do Período",
        tier="core",
    ),
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Audit FIGE CVM account-code and label stability across annual DFPs."
    )
    parser.add_argument("--start-year", type=int, default=2021)
    parser.add_argument("--end-year", type=int, default=2025)
    parser.add_argument(
        "--output",
        default="fige-statement-schema-stability-audit.json",
    )
    args = parser.parse_args()

    if args.start_year > args.end_year:
        raise ValueError("start-year must not be greater than end-year")

    collected_at = datetime.now(UTC)
    service = CVMIngestionService()
    reports_by_year = {}
    year_reference_dates: dict[str, str | None] = {}
    year_line_counts: dict[str, int] = {}

    for year in range(args.start_year, args.end_year + 1):
        lines = service.load_statements(
            document_type="DFP",
            year=year,
            statements=("BPA", "BPP", "DRE"),
            scope_token="ind",
            collected_at=collected_at,
        )
        report = audit_financial_statement_tree(
            lines,
            company_id=FIGE_COMPANY_ID,
            max_depth=4,
        )
        reports_by_year[year] = report
        year_reference_dates[str(year)] = (
            report.reference_date.isoformat() if report.reference_date else None
        )
        year_line_counts[str(year)] = len(report.lines)

    if not any(report.lines for report in reports_by_year.values()):
        raise RuntimeError(
            "CVM DFP returned no FIGE statement evidence for the requested year range"
        )

    stability = audit_statement_schema_stability(
        reports_by_year,
        company_id=FIGE_COMPANY_ID,
        candidates=FIGE_2025_SCHEMA_CANDIDATES,
        start_year=args.start_year,
        end_year=args.end_year,
    )

    review_candidates = [
        {
            "concept_id": result.concept_id,
            "statement": result.statement,
            "account_code": result.account_code,
            "tier": result.tier,
            "status": result.status,
            "missing_years": list(result.missing_years),
            "distinct_labels": list(result.distinct_labels),
        }
        for result in stability.results
        if result.status != STATUS_STABLE_EXACT
    ]
    core_review_candidates = [
        item for item in review_candidates if item["tier"] == "core"
    ]

    payload = {
        "generated_at": collected_at.isoformat(),
        "source": "CVM_DFP_CIA_ABERTA",
        "company_id": FIGE_COMPANY_ID,
        "start_year": args.start_year,
        "end_year": args.end_year,
        "statement_scope": "individual",
        "year_reference_dates": year_reference_dates,
        "year_line_counts": year_line_counts,
        "audit": stability.to_dict(),
        "review_candidates": review_candidates,
        "core_review_candidates": core_review_candidates,
        "notes": [
            "Diagnostic only: the candidate codes were selected from the previously validated FIGE 2025 official statement tree.",
            "The audit compares exact statement + account_code pairs across annual DFP snapshots and never infers equivalence from names.",
            "Label comparison preserves case and accents and normalizes whitespace only; any other label change is surfaced for review.",
            "An absent exact code remains missing/UNKNOWN and is never represented as zero.",
            "A stable label is evidence for a future FIGE accounting contract, not an automatic production mapping or scoring rule.",
            "Latest-state CVM annual archives are not treated as complete revision-history point-in-time evidence for historical backtests.",
        ],
    }
    Path(args.output).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, default=str)
        + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
