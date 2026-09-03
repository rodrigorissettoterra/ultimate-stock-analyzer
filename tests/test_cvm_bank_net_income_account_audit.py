from datetime import UTC, date, datetime

from ultimate_stock_analyzer.backtesting.cvm_bank_net_income_account_audit import (
    CVM_BANK_FIXED_311_NOT_OBSERVED,
    CVM_BANK_NET_INCOME_ACCOUNT_UNPROVEN,
    audit_cvm_bank_net_income_accounts,
)
from ultimate_stock_analyzer.domain.master import FinancialStatementLine


def _line(
    *,
    account_code: str,
    account_name: str,
    fiscal_year: int = 2024,
    cvm_code: int = 19348,
    fiscal_order: str = "ÚLTIMO",
) -> FinancialStatementLine:
    available_from = datetime(fiscal_year + 1, 3, 1, tzinfo=UTC)
    return FinancialStatementLine(
        company_id=f"cvm:{cvm_code}",
        cvm_code=cvm_code,
        company_name="BANCO TESTE",
        document_type="DFP",
        statement="DRE",
        consolidation_scope="DF Consolidado",
        reference_date=date(fiscal_year, 12, 31),
        period_start=date(fiscal_year, 1, 1),
        period_end=date(fiscal_year, 12, 31),
        fiscal_order=fiscal_order,
        account_code=account_code,
        account_name=account_name,
        value_brl=123.0,
        version=1,
        received_at=available_from,
        available_from=available_from,
        collected_at=available_from,
        source_document=f"dfp_cia_aberta_DRE_con_{fiscal_year}.csv",
    )


def test_audit_records_exact_fixed_311_without_promoting_mapping() -> None:
    audit = audit_cvm_bank_net_income_accounts(
        [_line(account_code="3.11", account_name="Lucro Líquido Consolidado")],
        cvm_code=19348,
        fiscal_year=2024,
    )

    assert audit.fixed_311_observed is True
    assert [item.account_code for item in audit.fixed_311_rows] == ["3.11"]
    assert [item.account_code for item in audit.heuristic_candidates] == ["3.11"]
    assert CVM_BANK_FIXED_311_NOT_OBSERVED not in audit.blockers
    assert CVM_BANK_NET_INCOME_ACCOUNT_UNPROVEN in audit.blockers
    assert audit.mapping_proven is False
    assert audit.readiness_promotion_allowed is False


def test_audit_surfaces_non_311_net_income_description_fail_closed() -> None:
    audit = audit_cvm_bank_net_income_accounts(
        [_line(account_code="3.09", account_name="Resultado Líquido do Período")],
        cvm_code=19348,
        fiscal_year=2024,
    )

    assert audit.fixed_311_observed is False
    assert [item.account_code for item in audit.heuristic_candidates] == ["3.09"]
    assert CVM_BANK_FIXED_311_NOT_OBSERVED in audit.blockers
    assert CVM_BANK_NET_INCOME_ACCOUNT_UNPROVEN in audit.blockers
    assert audit.mapping_proven is False


def test_audit_filters_other_years_issuers_and_fiscal_orders() -> None:
    lines = [
        _line(account_code="3.09", account_name="Lucro Líquido"),
        _line(
            account_code="3.11",
            account_name="Lucro Líquido",
            fiscal_year=2023,
        ),
        _line(
            account_code="3.11",
            account_name="Lucro Líquido",
            cvm_code=99999,
        ),
        _line(
            account_code="3.11",
            account_name="Lucro Líquido",
            fiscal_order="PENÚLTIMO",
        ),
    ]

    audit = audit_cvm_bank_net_income_accounts(
        lines,
        cvm_code=19348,
        fiscal_year=2024,
    )

    assert audit.dre_line_count == 1
    assert [item.account_code for item in audit.dre_accounts] == ["3.09"]
    assert CVM_BANK_FIXED_311_NOT_OBSERVED in audit.blockers


def test_audit_preserves_non_candidate_dre_rows_for_diagnostics() -> None:
    audit = audit_cvm_bank_net_income_accounts(
        [
            _line(account_code="3.01", account_name="Receitas da Intermediação"),
            _line(account_code="3.09", account_name="Prejuízo do Período"),
        ],
        cvm_code=19348,
        fiscal_year=2024,
    )

    assert [item.account_code for item in audit.dre_accounts] == ["3.01", "3.09"]
    assert [item.account_code for item in audit.heuristic_candidates] == ["3.09"]
    assert audit.to_dict()["readiness_promotion_allowed"] is False
