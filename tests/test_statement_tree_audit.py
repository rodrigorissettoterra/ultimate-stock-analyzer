from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from ultimate_stock_analyzer.domain.master import FinancialStatementLine
from ultimate_stock_analyzer.scoring.statement_tree_audit import (
    audit_financial_statement_tree,
)


def _line(
    statement: str,
    code: str,
    name: str,
    value: float,
    *,
    reference_date: date = date(2025, 12, 31),
    fiscal_order: str = "ÚLTIMO",
    version: int = 1,
    document_id: int = 1,
) -> FinancialStatementLine:
    return FinancialStatementLine(
        company_id="cvm:6041",
        cvm_code=6041,
        cnpj="01.548.981/0001-79",
        company_name="INVESTIMENTOS BEMGE S.A.",
        document_type="DFP",
        statement=statement,
        consolidation_scope="INDIVIDUAL",
        reference_date=reference_date,
        period_start=date(reference_date.year, 1, 1),
        period_end=reference_date,
        fiscal_order=fiscal_order,
        account_code=code,
        account_name=name,
        value_brl=value,
        version=version,
        document_id=document_id,
        available_from=datetime(2026, 3, 1, tzinfo=UTC),
        collected_at=datetime(2026, 9, 1, tzinfo=UTC),
    )


def test_statement_tree_audit_keeps_bounded_hierarchy() -> None:
    report = audit_financial_statement_tree(
        [
            _line("BPP", "2", "Passivo Total", 100.0),
            _line("BPP", "2.03", "Provisões", 20.0),
            _line("BPP", "2.03.01", "Provisão A", 10.0),
            _line("BPP", "2.03.01.01", "Detalhe", 5.0),
        ],
        company_id="cvm:6041",
        max_depth=3,
    )

    assert [item.account_code for item in report.lines] == ["2", "2.03", "2.03.01"]
    assert report.statement_counts == {"BPP": 3}
    assert report.reference_date == date(2025, 12, 31)


def test_statement_tree_audit_uses_latest_reference_and_revision() -> None:
    report = audit_financial_statement_tree(
        [
            _line(
                "DRE",
                "3.05",
                "Old year",
                1.0,
                reference_date=date(2024, 12, 31),
            ),
            _line("DRE", "3.05", "Old revision", 2.0, version=1, document_id=10),
            _line("DRE", "3.05", "Latest revision", 3.0, version=2, document_id=11),
        ],
        company_id="cvm:6041",
    )

    assert len(report.lines) == 1
    assert report.lines[0].account_name == "Latest revision"
    assert report.lines[0].value_brl == pytest.approx(3.0)


def test_statement_tree_audit_ignores_prior_fiscal_order() -> None:
    report = audit_financial_statement_tree(
        [
            _line("DRE", "3.01", "Current", 10.0),
            _line("DRE", "3.01", "Prior", 99.0, fiscal_order="PENÚLTIMO"),
        ],
        company_id="cvm:6041",
    )

    assert len(report.lines) == 1
    assert report.lines[0].account_name == "Current"
    assert report.lines[0].value_brl == pytest.approx(10.0)


def test_statement_tree_audit_missing_company_returns_empty_not_zero() -> None:
    report = audit_financial_statement_tree(
        [],
        company_id="cvm:6041",
    )

    assert report.reference_date is None
    assert report.lines == ()
    assert report.statement_counts == {}
    assert report.point_in_time_eligible is False


def test_statement_tree_audit_rejects_invalid_depth() -> None:
    with pytest.raises(ValueError, match="max_depth"):
        audit_financial_statement_tree(
            [],
            company_id="cvm:6041",
            max_depth=0,
        )
