from __future__ import annotations

from datetime import date

import pytest

from ultimate_stock_analyzer.scoring.itsa_holding_schema_stability import (
    ITSA_COMPANY_ID,
    audit_itsa_holding_schema_stability,
)
from ultimate_stock_analyzer.scoring.statement_schema_stability import (
    STATUS_LABEL_CHANGED,
    STATUS_MISSING,
    STATUS_STABLE_EXACT,
)
from ultimate_stock_analyzer.scoring.statement_tree_audit import (
    FinancialStatementTreeAuditReport,
    StatementTreeLine,
)

BASELINE_LABELS = {
    ("BPA", "1"): "Ativo Total",
    ("BPA", "1.02.02"): "Investimentos",
    ("BPA", "1.02.02.01"): "Participações Societárias",
    ("BPA", "1.02.02.01.04"): "Outros Investimentos",
    ("BPP", "2.03"): "Patrimônio Líquido",
    ("DRE", "3.04.06"): "Resultado de Equivalência Patrimonial",
    ("DRE", "3.11.01"): "Lucro ou Prejuízo Líquido Consolidado do Período",
}

BASELINE_VALUES = {
    ("BPA", "1"): 100.0,
    ("BPA", "1.02.02"): 90.0,
    ("BPA", "1.02.02.01"): 90.0,
    ("BPA", "1.02.02.01.04"): 1.0,
    ("BPP", "2.03"): 80.0,
    ("DRE", "3.04.06"): 11.0,
    ("DRE", "3.11.01"): 10.0,
}


def _report(
    year: int,
    *,
    labels: dict[tuple[str, str], str] | None = None,
    missing: set[tuple[str, str]] | None = None,
    values: dict[tuple[str, str], float] | None = None,
    company_id: str = ITSA_COMPANY_ID,
) -> FinancialStatementTreeAuditReport:
    labels = labels or {}
    missing = missing or set()
    values = values or {}
    lines = []
    for key, baseline_label in BASELINE_LABELS.items():
        if key in missing:
            continue
        statement, account_code = key
        lines.append(
            StatementTreeLine(
                statement=statement,
                account_code=account_code,
                account_name=labels.get(key, baseline_label),
                value_brl=values.get(key, BASELINE_VALUES[key]),
                depth=len(account_code.split(".")),
                consolidation_scope="INDIVIDUAL",
                document_type="DFP",
                version=1,
                document_id=year,
            )
        )
    return FinancialStatementTreeAuditReport(
        company_id=company_id,
        reference_date=date(year, 12, 31),
        max_depth=6,
        statement_counts={},
        lines=tuple(lines),
    )


def test_itsa_audit_uses_exact_2025_labels_and_keeps_parent_account_single_counted() -> None:
    reports = {year: _report(year) for year in range(2021, 2026)}

    audit = audit_itsa_holding_schema_stability(
        reports,
        start_year=2021,
        end_year=2025,
    )

    assert len(audit.candidates) == 7
    assert audit.all_core_schema_stable is True
    assert audit.schema_stability.status_counts == {STATUS_STABLE_EXACT: 7}

    by_concept = {candidate.concept_id: candidate for candidate in audit.candidates}
    assert by_concept["investments_total"].baseline_label == "Investimentos"
    assert (
        by_concept["equity_method_result"].baseline_label
        == "Resultado de Equivalência Patrimonial"
    )

    evidence = audit.year_evidence[-1]
    assert evidence.investments_to_assets == pytest.approx(0.9)
    assert evidence.equity_method_to_net_income == pytest.approx(1.1)
    assert evidence.equity_investments_to_investments == pytest.approx(1.0)
    assert evidence.other_investments_to_investments == pytest.approx(1.0 / 90.0)


def test_itsa_audit_surfaces_label_drift_and_missing_code_without_remapping() -> None:
    reports = {year: _report(year) for year in range(2021, 2026)}
    reports[2023] = _report(
        2023,
        labels={("BPA", "1.02.02"): "Investimentos Permanentes"},
    )
    reports[2022] = _report(
        2022,
        missing={("BPA", "1.02.02.01.04")},
    )

    audit = audit_itsa_holding_schema_stability(
        reports,
        start_year=2021,
        end_year=2025,
    )
    results = {
        result.concept_id: result for result in audit.schema_stability.results
    }

    assert results["investments_total"].status == STATUS_LABEL_CHANGED
    assert results["other_investments"].status == STATUS_MISSING
    assert results["other_investments"].missing_years == (2022,)
    assert audit.all_core_schema_stable is False

    evidence_2022 = next(
        row for row in audit.year_evidence if row.fiscal_year == 2022
    )
    assert evidence_2022.other_investments is None
    assert evidence_2022.investments_to_assets == pytest.approx(0.9)


def test_itsa_audit_fails_closed_when_baseline_exact_code_is_missing() -> None:
    reports = {year: _report(year) for year in range(2021, 2026)}
    reports[2025] = _report(
        2025,
        missing={("DRE", "3.04.06")},
    )

    with pytest.raises(ValueError, match="baseline schema code must resolve exactly once"):
        audit_itsa_holding_schema_stability(
            reports,
            start_year=2021,
            end_year=2025,
        )


def test_itsa_audit_rejects_wrong_baseline_identity() -> None:
    reports = {year: _report(year) for year in range(2021, 2026)}
    reports[2025] = _report(2025, company_id="cvm:9999")

    with pytest.raises(ValueError, match="baseline report company identity mismatch"):
        audit_itsa_holding_schema_stability(
            reports,
            start_year=2021,
            end_year=2025,
        )
