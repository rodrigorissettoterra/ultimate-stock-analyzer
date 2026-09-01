from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from ultimate_stock_analyzer.domain.master import FinancialStatementLine
from ultimate_stock_analyzer.fundamentals.contracts import GENERAL_CORPORATE_CONTRACT
from ultimate_stock_analyzer.fundamentals.cvm_accounts import GENERAL_CORPORATE_FIXED_ACCOUNTS
from ultimate_stock_analyzer.scoring.b100_accounting_lifecycle import (
    B100_COMPANY_ID,
    B100_CVM_CODE,
    audit_b100_accounting_lifecycle,
)

COLLECTED_AT = datetime(2026, 9, 1, tzinfo=UTC)


def _line(
    statement: str,
    account_code: str,
    account_name: str,
    value: float,
    *,
    company_id: str = B100_COMPANY_ID,
    cvm_code: int = B100_CVM_CODE,
    reference_date: date = date(2025, 12, 31),
    document_type: str = "DFP",
    scope: str = "DF Individual",
) -> FinancialStatementLine:
    return FinancialStatementLine(
        company_id=company_id,
        cvm_code=cvm_code,
        company_name="B100 S.A.",
        document_type=document_type,
        statement=statement,
        consolidation_scope=scope,
        reference_date=reference_date,
        fiscal_order="ÚLTIMO",
        account_code=account_code,
        account_name=account_name,
        value_brl=value,
        version=1,
        collected_at=COLLECTED_AT,
        source_document=f"{statement.lower()}_test.csv",
    )


def _general_corporate_complete_lines() -> list[FinancialStatementLine]:
    required = set(GENERAL_CORPORATE_CONTRACT.critical_inputs)
    lines: list[FinancialStatementLine] = []
    labels = {
        "total_assets": "Ativo Total",
        "equity": "Patrimônio Líquido",
    }
    for account in GENERAL_CORPORATE_FIXED_ACCOUNTS:
        if account.name not in required:
            continue
        statement = account.statements[0]
        lines.append(
            _line(
                statement,
                account.code,
                labels.get(account.name, account.name),
                100.0,
            )
        )
    return lines


def _holding_complete_lines() -> list[FinancialStatementLine]:
    return [
        _line("BPA", "1", "Ativo Total", 1_000.0),
        _line("BPA", "1.02.02", "Investimentos", 900.0),
        _line("BPA", "1.02.02.01", "Participações Societárias", 900.0),
        _line("BPA", "1.02.02.01.04", "Outros Investimentos", 0.0),
        _line("BPP", "2.03", "Patrimônio Líquido", 800.0),
        _line("DRE", "3.04.06", "Resultado de Equivalência Patrimonial", 120.0),
        _line("DRE", "3.11", "Lucro/Prejuízo do Período", 100.0),
    ]


def test_lifecycle_keeps_general_corporate_and_holding_evidence_independent() -> None:
    report = audit_b100_accounting_lifecycle(
        {
            ("DFP", 2024, "ind"): _general_corporate_complete_lines(),
            ("DFP", 2025, "ind"): _holding_complete_lines(),
        }
    )

    by_id = {item.snapshot_id: item for item in report.snapshots}
    general = by_id["DFP_2024_ind"]
    holding = by_id["DFP_2025_ind"]

    assert general.general_corporate_critical_coverage == 1.0
    assert general.holding_critical_schema_coverage < 1.0
    assert holding.holding_critical_schema_coverage == 1.0
    assert holding.general_corporate_critical_coverage < 1.0
    assert report.general_corporate_full_critical_snapshot_ids == ("DFP_2024_ind",)
    assert report.holding_full_critical_schema_snapshot_ids == ("DFP_2025_ind",)
    assert report.routing_ready is False
    assert report.scoring_ready is False
    assert report.applicability_registry_resolvable is False


def test_lifecycle_preserves_missing_snapshot_as_no_evidence_not_zero() -> None:
    report = audit_b100_accounting_lifecycle(
        {
            ("DFP", 2024, "ind"): [],
            ("DFP", 2025, "ind"): _holding_complete_lines(),
        }
    )

    missing = next(item for item in report.snapshots if item.snapshot_id == "DFP_2024_ind")
    assert missing.reference_date is None
    assert missing.line_count == 0
    assert missing.total_assets is None
    assert missing.investments_total is None
    assert missing.net_income is None
    assert missing.investments_to_assets is None
    assert missing.general_corporate_critical_coverage == 0.0
    assert missing.holding_critical_schema_coverage == 0.0
    assert report.evidence_snapshot_count == 1


def test_lifecycle_rejects_foreign_company_identity() -> None:
    lines = [
        _line(
            "BPA",
            "1",
            "Ativo Total",
            100.0,
            company_id="cvm:9999",
            cvm_code=9999,
        )
    ]

    with pytest.raises(ValueError, match="company identity mismatch"):
        audit_b100_accounting_lifecycle({("DFP", 2025, "ind"): lines})
