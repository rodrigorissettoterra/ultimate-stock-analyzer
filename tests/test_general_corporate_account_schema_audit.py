from __future__ import annotations

from datetime import UTC, date, datetime

from ultimate_stock_analyzer.domain.master import FinancialStatementLine
from ultimate_stock_analyzer.scoring.account_schema_audit import (
    audit_general_corporate_account_schema,
)


def _line(
    company_id: str,
    statement: str,
    code: str,
    name: str,
    value: float,
    *,
    version: int = 1,
    document_id: int = 1,
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
        version=version,
        document_id=document_id,
        available_from=datetime(2026, 3, 1, tzinfo=UTC),
        collected_at=datetime(2026, 9, 1, tzinfo=UTC),
    )


def _concept(report, name: str):
    return next(item for item in report.concepts if item.concept_name == name)


def test_account_schema_audit_flags_different_official_labels_without_equating_them() -> None:
    report = audit_general_corporate_account_schema(
        [
            _line(
                "cvm:1",
                "DRE",
                "3.01",
                "Receita de Venda de Bens e/ou Serviços",
                100.0,
            ),
            _line(
                "cvm:2",
                "DRE",
                "3.01",
                "Receitas da Intermediação Financeira",
                200.0,
            ),
        ],
        company_ids=("cvm:1", "cvm:2"),
    )

    revenue = _concept(report, "revenue")

    assert revenue.status == "DIVERGENT_ACCOUNT_LABEL"
    assert revenue.observed_company_count == 2
    assert revenue.missing_company_ids == ()
    assert revenue.normalized_account_names == (
        "receita de venda de bens e/ou servicos",
        "receitas da intermediacao financeira",
    )
    assert "revenue" in report.divergent_concepts


def test_account_schema_audit_preserves_partial_coverage_as_missing() -> None:
    report = audit_general_corporate_account_schema(
        [_line("cvm:1", "BPP", "2.03", "Patrimônio Líquido", 100.0)],
        company_ids=("cvm:1", "cvm:2"),
    )

    equity = _concept(report, "equity")

    assert equity.status == "PARTIAL_COVERAGE"
    assert equity.observed_company_count == 1
    assert equity.missing_company_ids == ("cvm:2",)
    assert "equity" in report.partial_coverage_concepts


def test_account_schema_audit_uses_latest_revision_for_exact_code() -> None:
    report = audit_general_corporate_account_schema(
        [
            _line(
                "cvm:1",
                "DRE",
                "3.05",
                "Resultado Antes do Resultado Financeiro e dos Tributos",
                10.0,
                version=1,
                document_id=10,
            ),
            _line(
                "cvm:1",
                "DRE",
                "3.05",
                "Resultado Operacional",
                20.0,
                version=2,
                document_id=11,
            ),
        ],
        company_ids=("cvm:1",),
    )

    ebit = _concept(report, "ebit")

    assert ebit.status == "CONSISTENT_ACCOUNT_LABEL"
    assert len(ebit.observations) == 1
    assert ebit.observations[0].account_name == "Resultado Operacional"
    assert ebit.observations[0].value_brl == 20.0


def test_account_schema_audit_never_invents_zero_for_missing_code() -> None:
    report = audit_general_corporate_account_schema(
        [],
        company_ids=("cvm:999",),
    )

    revenue = _concept(report, "revenue")

    assert revenue.status == "MISSING_ALL"
    assert revenue.observations == ()
    assert revenue.missing_company_ids == ("cvm:999",)
    assert "revenue" in report.missing_all_concepts
