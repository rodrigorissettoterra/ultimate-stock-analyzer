from __future__ import annotations

from datetime import date

import pytest

from ultimate_stock_analyzer.fundamentals.itsa_holding_contract import (
    ITSA_COMPANY_ID,
    ITSA_HOLDING_ACCOUNT_BINDINGS,
    evaluate_itsa_holding_contract,
)
from ultimate_stock_analyzer.scoring.statement_tree_audit import (
    FinancialStatementTreeAuditReport,
    StatementTreeLine,
)


def _report(
    *,
    company_id: str = ITSA_COMPANY_ID,
    missing_concepts: set[str] | None = None,
    label_overrides: dict[str, str] | None = None,
) -> FinancialStatementTreeAuditReport:
    missing_concepts = missing_concepts or set()
    label_overrides = label_overrides or {}
    values = {
        "total_assets": 100.0,
        "investments_total": 90.0,
        "equity_investments": 90.0,
        "other_investments": 1.0,
        "equity": 80.0,
        "equity_method_result": 11.0,
        "net_income_parent": 10.0,
    }
    lines = tuple(
        StatementTreeLine(
            statement=binding.statement,
            account_code=binding.account_code,
            account_name=label_overrides.get(
                binding.concept_id,
                binding.expected_label,
            ),
            value_brl=values[binding.concept_id],
            depth=len(binding.account_code.split(".")),
            consolidation_scope="INDIVIDUAL",
            document_type="DFP",
            version=1,
            document_id=1,
        )
        for binding in ITSA_HOLDING_ACCOUNT_BINDINGS
        if binding.concept_id not in missing_concepts
    )
    return FinancialStatementTreeAuditReport(
        company_id=company_id,
        reference_date=date(2025, 12, 31),
        max_depth=6,
        statement_counts={},
        lines=lines,
    )


def test_itsa_holding_contract_extracts_exact_binding_set_and_metrics() -> None:
    evaluation = evaluate_itsa_holding_contract(_report())

    assert set(evaluation.values) == {
        binding.concept_id for binding in ITSA_HOLDING_ACCOUNT_BINDINGS
    }
    assert evaluation.coverage.critical_coverage == pytest.approx(1.0)
    assert evaluation.coverage.total_coverage == pytest.approx(1.0)
    assert evaluation.descriptive_metrics["investments_to_assets"] == pytest.approx(
        0.9
    )
    assert evaluation.descriptive_metrics[
        "equity_method_to_net_income"
    ] == pytest.approx(1.1)
    assert evaluation.descriptive_metrics[
        "equity_investments_to_investments"
    ] == pytest.approx(1.0)


def test_itsa_holding_contract_does_not_double_count_nested_investment_rows() -> None:
    evaluation = evaluate_itsa_holding_contract(_report())

    assert evaluation.values["investments_total"] == 90.0
    assert evaluation.values["equity_investments"] == 90.0
    assert evaluation.values["other_investments"] == 1.0
    assert evaluation.descriptive_metrics["investments_to_assets"] == pytest.approx(
        0.9
    )
    assert evaluation.descriptive_metrics[
        "other_investments_to_investments"
    ] == pytest.approx(1.0 / 90.0)


def test_itsa_holding_contract_fails_closed_on_exact_label_drift() -> None:
    with pytest.raises(ValueError, match="holding account label mismatch"):
        evaluate_itsa_holding_contract(
            _report(
                label_overrides={
                    "investments_total": "Investimentos Permanentes",
                }
            )
        )


def test_itsa_holding_contract_reports_missing_supporting_input_as_unknown() -> None:
    evaluation = evaluate_itsa_holding_contract(
        _report(missing_concepts={"other_investments"})
    )

    assert evaluation.coverage.critical_coverage == pytest.approx(1.0)
    assert evaluation.coverage.total_coverage < 1.0
    assert evaluation.coverage.missing_supporting == ("other_investments",)
    assert (
        evaluation.descriptive_metrics["other_investments_to_investments"]
        is None
    )


def test_itsa_holding_contract_rejects_wrong_company_identity() -> None:
    with pytest.raises(ValueError, match="company identity mismatch"):
        evaluate_itsa_holding_contract(_report(company_id="cvm:9999"))
