from __future__ import annotations

from datetime import UTC, date, datetime

from ultimate_stock_analyzer.domain.master import FinancialStatementLine
from ultimate_stock_analyzer.scoring.holding_model_audit import (
    audit_holding_model_data_contract,
)


def _line(
    company_id: str,
    statement: str,
    code: str,
    name: str,
    value: float,
) -> FinancialStatementLine:
    return FinancialStatementLine(
        company_id=company_id,
        cvm_code=int(company_id.split(":", 1)[1]),
        cnpj=None,
        company_name=company_id,
        document_type="DFP",
        statement=statement,
        consolidation_scope="INDIVIDUAL",
        reference_date=date(2025, 12, 31),
        period_start=date(2025, 1, 1),
        period_end=date(2025, 12, 31),
        fiscal_order="ÚLTIMO",
        account_code=code,
        account_name=name,
        value_brl=value,
        version=1,
        document_id=1,
        available_from=datetime(2026, 3, 1, tzinfo=UTC),
        collected_at=datetime(2026, 9, 1, tzinfo=UTC),
    )


def test_holding_audit_surfaces_equity_method_and_investment_evidence() -> None:
    lines = [
        _line("cvm:1", "BPA", "1", "Ativo Total", 1000.0),
        _line("cvm:1", "BPA", "1.01.01", "Caixa e Equivalentes de Caixa", 50.0),
        _line("cvm:1", "BPA", "1.02.03", "Investimentos", 700.0),
        _line("cvm:1", "BPP", "2.01.04", "Empréstimos e Financiamentos", 20.0),
        _line("cvm:1", "BPP", "2.02.01", "Empréstimos e Financiamentos", 80.0),
        _line("cvm:1", "BPP", "2.03", "Patrimônio Líquido", 800.0),
        _line("cvm:1", "DRE", "3.06.01", "Resultado de Equivalência Patrimonial", 180.0),
        _line("cvm:1", "DRE", "3.11.01", "Lucro Líquido", 200.0),
    ]

    report = audit_holding_model_data_contract(lines, company_ids=("cvm:1",))
    audit = report.company_audits[0]

    assert audit.investment_candidates_total == 700.0
    assert audit.equity_method_candidates_total == 180.0
    assert audit.investments_to_assets == 0.7
    assert audit.equity_method_to_net_income == 0.9
    assert audit.gross_borrowings == 100.0
    assert audit.cash_and_current_financial_investments == 50.0
    assert audit.warnings == ()


def test_holding_audit_withholds_candidate_total_when_matches_can_double_count() -> None:
    lines = [
        _line("cvm:1", "BPA", "1", "Ativo Total", 1000.0),
        _line("cvm:1", "BPA", "1.02.03", "Investimentos", 700.0),
        _line("cvm:1", "BPA", "1.02.03.01", "Investimentos em Controladas", 500.0),
        _line("cvm:1", "DRE", "3.11.01", "Lucro Líquido", 200.0),
    ]

    audit = audit_holding_model_data_contract(
        lines,
        company_ids=("cvm:1",),
    ).company_audits[0]

    assert audit.investment_candidates_total is None
    assert audit.investments_to_assets is None
    assert "MULTIPLE_INVESTMENT_ACCOUNT_CANDIDATES" in audit.warnings
    assert "NO_EQUITY_METHOD_ACCOUNT_CANDIDATE" in audit.warnings


def test_holding_audit_keeps_missing_company_unknown_not_zero() -> None:
    audit = audit_holding_model_data_contract(
        [],
        company_ids=("cvm:999",),
    ).company_audits[0]

    assert audit.reference_date is None
    assert audit.total_assets is None
    assert audit.investment_candidates_total is None
    assert audit.equity_method_candidates_total is None
    assert "NO_DFP_LINES_FOR_COMPANY" in audit.warnings
