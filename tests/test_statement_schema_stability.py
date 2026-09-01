from __future__ import annotations

from datetime import date

import pytest

from ultimate_stock_analyzer.scoring.statement_schema_stability import (
    STATUS_LABEL_CHANGED,
    STATUS_MISSING,
    STATUS_STABLE_EXACT,
    StatementSchemaCandidate,
    audit_statement_schema_stability,
)
from ultimate_stock_analyzer.scoring.statement_tree_audit import (
    FinancialStatementTreeAuditReport,
    StatementTreeLine,
)


def _report(
    year: int,
    *,
    company_id: str = "cvm:6041",
    label: str | None = "Patrimônio Líquido",
) -> FinancialStatementTreeAuditReport:
    lines = ()
    if label is not None:
        lines = (
            StatementTreeLine(
                statement="BPP",
                account_code="2.07",
                account_name=label,
                value_brl=100.0 + year,
                depth=2,
                consolidation_scope="INDIVIDUAL",
                document_type="DFP",
                version=1,
                document_id=year,
            ),
        )
    return FinancialStatementTreeAuditReport(
        company_id=company_id,
        reference_date=date(year, 12, 31),
        max_depth=4,
        statement_counts={"BPP": len(lines)},
        lines=lines,
    )


def _candidate() -> StatementSchemaCandidate:
    return StatementSchemaCandidate(
        concept_id="equity",
        statement="BPP",
        account_code="2.07",
        baseline_label="Patrimônio Líquido",
        tier="core",
    )


def test_schema_stability_accepts_exact_label_across_full_window() -> None:
    reports = {year: _report(year) for year in range(2021, 2026)}

    audit = audit_statement_schema_stability(
        reports,
        company_id="cvm:6041",
        candidates=(_candidate(),),
        start_year=2021,
        end_year=2025,
    )

    result = audit.results[0]
    assert result.status == STATUS_STABLE_EXACT
    assert result.missing_years == ()
    assert result.distinct_labels == ("Patrimônio Líquido",)
    assert audit.status_counts == {STATUS_STABLE_EXACT: 1}
    assert audit.point_in_time_eligible is False


def test_schema_stability_surfaces_exact_code_label_change_for_review() -> None:
    reports = {year: _report(year) for year in range(2021, 2026)}
    reports[2023] = _report(2023, label="Patrimônio Líquido Total")

    audit = audit_statement_schema_stability(
        reports,
        company_id="cvm:6041",
        candidates=(_candidate(),),
        start_year=2021,
        end_year=2025,
    )

    result = audit.results[0]
    assert result.status == STATUS_LABEL_CHANGED
    assert result.missing_years == ()
    assert result.distinct_labels == (
        "Patrimônio Líquido",
        "Patrimônio Líquido Total",
    )


def test_schema_stability_keeps_absent_code_missing_unknown() -> None:
    reports = {year: _report(year) for year in range(2021, 2026)}
    reports[2022] = _report(2022, label=None)

    audit = audit_statement_schema_stability(
        reports,
        company_id="cvm:6041",
        candidates=(_candidate(),),
        start_year=2021,
        end_year=2025,
    )

    result = audit.results[0]
    assert result.status == STATUS_MISSING
    assert result.missing_years == (2022,)
    observation = next(row for row in result.observations if row.fiscal_year == 2022)
    assert observation.value_brl is None
    assert observation.account_name is None


def test_schema_stability_rejects_mismatched_company_identity() -> None:
    reports = {2025: _report(2025, company_id="cvm:9999")}

    with pytest.raises(ValueError, match="company identity mismatch"):
        audit_statement_schema_stability(
            reports,
            company_id="cvm:6041",
            candidates=(_candidate(),),
            start_year=2025,
            end_year=2025,
        )
