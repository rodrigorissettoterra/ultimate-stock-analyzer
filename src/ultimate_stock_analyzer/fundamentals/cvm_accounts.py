from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from ultimate_stock_analyzer.domain.master import FinancialStatementLine


@dataclass(frozen=True, slots=True)
class FixedAccount:
    name: str
    statements: tuple[str, ...]
    code: str


GENERAL_CORPORATE_FIXED_ACCOUNTS: tuple[FixedAccount, ...] = (
    FixedAccount("total_assets", ("BPA",), "1"),
    FixedAccount("current_assets", ("BPA",), "1.01"),
    FixedAccount("cash_and_equivalents", ("BPA",), "1.01.01"),
    FixedAccount("financial_investments_current", ("BPA",), "1.01.02"),
    FixedAccount("receivables_current", ("BPA",), "1.01.03"),
    FixedAccount("inventories_current", ("BPA",), "1.01.04"),
    FixedAccount("total_liabilities_and_equity", ("BPP",), "2"),
    FixedAccount("current_liabilities", ("BPP",), "2.01"),
    FixedAccount("suppliers_current", ("BPP",), "2.01.02"),
    FixedAccount("borrowings_current", ("BPP",), "2.01.04"),
    FixedAccount("noncurrent_liabilities", ("BPP",), "2.02"),
    FixedAccount("borrowings_noncurrent", ("BPP",), "2.02.01"),
    FixedAccount("equity", ("BPP",), "2.03"),
    FixedAccount("revenue", ("DRE",), "3.01"),
    FixedAccount("cost_of_goods_and_services", ("DRE",), "3.02"),
    FixedAccount("gross_profit", ("DRE",), "3.03"),
    FixedAccount("ebit", ("DRE",), "3.05"),
    FixedAccount("pretax_income", ("DRE",), "3.07"),
    FixedAccount("income_tax", ("DRE",), "3.08"),
    FixedAccount("net_income_consolidated", ("DRE",), "3.11"),
    FixedAccount("net_income_parent", ("DRE",), "3.11.01"),
    FixedAccount("cash_from_operations", ("DFC_MD", "DFC_MI"), "6.01"),
    FixedAccount("cash_from_investing", ("DFC_MD", "DFC_MI"), "6.02"),
    FixedAccount("cash_from_financing", ("DFC_MD", "DFC_MI"), "6.03"),
    FixedAccount("depreciation_and_amortization", ("DVA",), "7.04.01"),
)


@dataclass(frozen=True, slots=True)
class AccountExtraction:
    values: dict[str, float]
    lines: dict[str, FinancialStatementLine]
    missing: tuple[str, ...]


def extract_fixed_accounts(
    lines: list[FinancialStatementLine],
    *,
    company_id: str,
    reference_date: date,
    consolidation_scope: str | None = None,
    fiscal_order: str = "ÚLTIMO",
) -> AccountExtraction:
    candidates = [
        line
        for line in lines
        if line.company_id == company_id
        and line.reference_date == reference_date
        and line.fiscal_order == fiscal_order
        and (
            consolidation_scope is None
            or line.consolidation_scope == consolidation_scope
        )
    ]
    if consolidation_scope is None:
        candidates = _prefer_accounting_scope(candidates)

    values: dict[str, float] = {}
    lineage: dict[str, FinancialStatementLine] = {}
    missing: list[str] = []

    for account in GENERAL_CORPORATE_FIXED_ACCOUNTS:
        matches = [
            line
            for line in candidates
            if line.statement in account.statements and line.account_code == account.code
        ]
        if not matches:
            missing.append(account.name)
            continue
        selected = max(matches, key=_revision_rank)
        values[account.name] = selected.value_brl
        lineage[account.name] = selected

    return AccountExtraction(
        values=values,
        lines=lineage,
        missing=tuple(missing),
    )


def _prefer_accounting_scope(
    candidates: list[FinancialStatementLine],
) -> list[FinancialStatementLine]:
    """Choose one accounting scope before extracting any fixed account.

    CVM issuers can publish individual and consolidated statements for the same
    reference date. Mixing them account-by-account produces internally inconsistent
    metrics. Consolidated statements represent the economic group and are preferred
    whenever present; individual statements are used only when no consolidated rows
    exist for the issuer/reference date.
    """

    scope_kinds = {_scope_kind(line.consolidation_scope) for line in candidates}
    if "consolidated" in scope_kinds:
        return [
            line
            for line in candidates
            if _scope_kind(line.consolidation_scope) == "consolidated"
        ]
    if "individual" in scope_kinds:
        return [
            line
            for line in candidates
            if _scope_kind(line.consolidation_scope) == "individual"
        ]
    return candidates


def _scope_kind(value: str | None) -> str:
    normalized = str(value or "").casefold()
    if "consolid" in normalized:
        return "consolidated"
    if "individual" in normalized:
        return "individual"
    return "other"


def _revision_rank(line: FinancialStatementLine) -> tuple[int, int]:
    return line.version, line.document_id or -1
