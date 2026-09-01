from __future__ import annotations

from datetime import date

import pytest

from ultimate_stock_analyzer.fundamentals.itsa_holding_contract import (
    ITSA_HOLDING_ACCOUNT_BINDINGS,
)
from ultimate_stock_analyzer.scoring.holding_segment_economic_stability import (
    HoldingSegmentMember,
    audit_holding_segment_economic_stability,
)
from ultimate_stock_analyzer.scoring.statement_tree_audit import (
    FinancialStatementTreeAuditReport,
    StatementTreeLine,
)


def _member(company_id: str, cvm_code: int, issuer_code: str) -> HoldingSegmentMember:
    return HoldingSegmentMember(
        company_id=company_id,
        cvm_code=cvm_code,
        issuer_code=issuer_code,
        trading_name=issuer_code,
        sector="Financeiro",
        subsector="Holdings Diversificadas",
        segment="Holdings Diversificadas",
        model_id="general_corporate",
    )


def _report(
    company_id: str,
    year: int,
    *,
    scale: float = 1.0,
    missing: set[str] | None = None,
    mismatched: set[str] | None = None,
) -> FinancialStatementTreeAuditReport:
    missing = missing or set()
    mismatched = mismatched or set()
    values = {
        "total_assets": 100.0 * scale,
        "investments_total": 90.0 * scale,
        "equity_investments": 90.0 * scale,
        "other_investments": 1.0 * scale,
        "equity": 80.0 * scale,
        "equity_method_result": 11.0 * scale,
        "net_income_parent": 10.0 * scale,
    }
    lines = []
    for binding in ITSA_HOLDING_ACCOUNT_BINDINGS:
        if binding.concept_id in missing:
            continue
        lines.append(
            StatementTreeLine(
                statement=binding.statement,
                account_code=binding.account_code,
                account_name=(
                    f"{binding.expected_label} ALTERADO"
                    if binding.concept_id in mismatched
                    else binding.expected_label
                ),
                value_brl=values[binding.concept_id],
                depth=len(binding.account_code.split(".")),
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


def test_segment_audit_summarizes_exact_schema_and_descriptive_ranges() -> None:
    members = (
        _member("cvm:7617", 7617, "ITSA"),
        _member("cvm:100", 100, "PEER"),
    )
    reports = {}
    for year, scale in ((2024, 1.0), (2025, 2.0)):
        reports[("cvm:7617", year)] = _report("cvm:7617", year, scale=scale)
        reports[("cvm:100", year)] = _report("cvm:100", year, scale=scale)

    audit = audit_holding_segment_economic_stability(
        members=members,
        reports_by_company_year=reports,
        anchor_company_id="cvm:7617",
        start_year=2024,
        end_year=2025,
    )

    assert audit.member_count == 2
    assert audit.all_members_have_statement_evidence is True
    assert audit.all_members_critical_schema_complete_all_observed_years is True
    itsa = next(item for item in audit.company_summaries if item.company_id == "cvm:7617")
    assert itsa.critical_schema_complete_years == (2024, 2025)
    assert itsa.full_schema_exact_years == (2024, 2025)
    investments = itsa.metric_ranges["investments_to_assets"]
    assert investments.observations == 2
    assert investments.minimum == pytest.approx(0.9)
    assert investments.maximum == pytest.approx(0.9)
    assert investments.median == pytest.approx(0.9)
    assert audit.segment_routing_ready is False
    assert audit.applicability_registry_resolvable is False


def test_missing_statement_year_and_schema_drift_remain_explicit() -> None:
    members = (
        _member("cvm:7617", 7617, "ITSA"),
        _member("cvm:100", 100, "PEER"),
    )
    reports = {
        ("cvm:7617", 2024): _report("cvm:7617", 2024),
        ("cvm:7617", 2025): _report("cvm:7617", 2025),
        ("cvm:100", 2025): _report(
            "cvm:100",
            2025,
            mismatched={"equity_method_result"},
        ),
    }

    audit = audit_holding_segment_economic_stability(
        members=members,
        reports_by_company_year=reports,
        anchor_company_id="cvm:7617",
        start_year=2024,
        end_year=2025,
    )

    assert audit.all_members_have_statement_evidence is False
    peer = next(item for item in audit.company_summaries if item.company_id == "cvm:100")
    assert peer.missing_statement_years == (2024,)
    assert peer.critical_schema_complete_years == ()
    assert peer.critical_schema_complete_all_observed_years is False
    peer_2024 = next(
        row
        for row in audit.year_evidence
        if row.company_id == "cvm:100" and row.fiscal_year == 2024
    )
    assert peer_2024.statement_evidence_present is False
    assert peer_2024.values == {}
    assert peer_2024.descriptive_metrics["investments_to_assets"] is None


def test_segment_audit_rejects_member_outside_anchor_classification() -> None:
    anchor = _member("cvm:7617", 7617, "ITSA")
    outside = HoldingSegmentMember(
        company_id="cvm:100",
        cvm_code=100,
        issuer_code="OUT",
        trading_name="OUT",
        sector="Financeiro",
        subsector="Serviços Financeiros Diversos",
        segment="Gestão de Recursos e Investimentos",
        model_id="general_corporate",
    )

    with pytest.raises(ValueError, match="share the anchor exact B3 classification"):
        audit_holding_segment_economic_stability(
            members=(anchor, outside),
            reports_by_company_year={},
            anchor_company_id="cvm:7617",
            start_year=2025,
            end_year=2025,
        )


def test_statement_report_identity_mismatch_fails_closed() -> None:
    member = _member("cvm:7617", 7617, "ITSA")
    wrong = _report("cvm:9999", 2025)

    with pytest.raises(ValueError, match="statement report identity mismatch"):
        audit_holding_segment_economic_stability(
            members=(member,),
            reports_by_company_year={("cvm:7617", 2025): wrong},
            anchor_company_id="cvm:7617",
            start_year=2025,
            end_year=2025,
        )
