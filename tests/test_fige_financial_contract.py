from __future__ import annotations

from datetime import date

import pytest

from ultimate_stock_analyzer.fundamentals.fige_financial_contract import (
    FIGE_FINANCIAL_ACCOUNT_BINDINGS,
    evaluate_fige_financial_contract,
)
from ultimate_stock_analyzer.scoring.statement_tree_audit import (
    FinancialStatementTreeAuditReport,
    StatementTreeLine,
)


def _report(
    *,
    company_id: str = "cvm:6041",
    drop_concept: str | None = None,
    mutate_label: str | None = None,
) -> FinancialStatementTreeAuditReport:
    rows: list[StatementTreeLine] = []
    for index, binding in enumerate(FIGE_FINANCIAL_ACCOUNT_BINDINGS, start=1):
        if binding.concept_id == drop_concept:
            continue
        label = binding.expected_label
        if binding.concept_id == "equity" and mutate_label is not None:
            label = mutate_label
        value = (
            0.0
            if binding.concept_id == "financial_intermediation_expense"
            else float(index)
        )
        rows.append(
            StatementTreeLine(
                statement=binding.statement,
                account_code=binding.account_code,
                account_name=label,
                value_brl=value,
                depth=len(binding.account_code.split(".")),
                consolidation_scope="INDIVIDUAL",
                document_type="DFP",
                version=1,
                document_id=100 + index,
            )
        )
    statement_counts = {
        statement: sum(1 for row in rows if row.statement == statement)
        for statement in {row.statement for row in rows}
    }
    return FinancialStatementTreeAuditReport(
        company_id=company_id,
        reference_date=date(2025, 12, 31),
        max_depth=4,
        statement_counts=statement_counts,
        lines=tuple(rows),
    )


def test_fige_financial_contract_is_complete_for_exact_stable_schema() -> None:
    evaluation = evaluate_fige_financial_contract(_report())

    assert evaluation.coverage.critical_coverage == pytest.approx(1.0)
    assert evaluation.coverage.total_coverage == pytest.approx(1.0)
    assert evaluation.coverage.missing_critical == ()
    assert evaluation.coverage.missing_supporting == ()
    assert evaluation.values["financial_intermediation_expense"] == 0.0
    assert evaluation.effect == "contract_defined_not_routed"
    assert evaluation.point_in_time_eligible is False


def test_fige_financial_contract_keeps_missing_supporting_input_unknown() -> None:
    evaluation = evaluate_fige_financial_contract(
        _report(drop_concept="provisions")
    )

    assert evaluation.coverage.critical_coverage == pytest.approx(1.0)
    assert evaluation.coverage.total_coverage < 1.0
    assert evaluation.coverage.missing_supporting == ("provisions",)
    assert "provisions" not in evaluation.values


def test_fige_financial_contract_marks_missing_critical_input() -> None:
    evaluation = evaluate_fige_financial_contract(
        _report(drop_concept="equity")
    )

    assert evaluation.coverage.critical_coverage < 1.0
    assert evaluation.coverage.missing_critical == ("equity",)
    assert "equity" not in evaluation.values


def test_fige_financial_contract_fails_closed_on_label_change() -> None:
    with pytest.raises(ValueError, match="account label mismatch"):
        evaluate_fige_financial_contract(
            _report(mutate_label="Patrimônio Líquido Total")
        )


def test_fige_financial_contract_rejects_other_company_identity() -> None:
    with pytest.raises(ValueError, match="company identity mismatch"):
        evaluate_fige_financial_contract(_report(company_id="cvm:9999"))
