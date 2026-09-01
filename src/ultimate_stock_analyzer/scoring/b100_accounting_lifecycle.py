from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date

from ultimate_stock_analyzer.domain.master import FinancialStatementLine
from ultimate_stock_analyzer.fundamentals.contracts import (
    GENERAL_CORPORATE_CONTRACT,
    evaluate_contract,
)
from ultimate_stock_analyzer.fundamentals.cvm_accounts import extract_fixed_accounts
from ultimate_stock_analyzer.fundamentals.metrics import safe_div
from ultimate_stock_analyzer.scoring.itsa_peer_discovery import compare_itsa_holding_schema
from ultimate_stock_analyzer.scoring.statement_tree_audit import (
    audit_financial_statement_tree,
)

B100_COMPANY_ID = "cvm:27634"
B100_CVM_CODE = 27634


@dataclass(frozen=True, slots=True)
class B100AccountingSnapshot:
    snapshot_id: str
    document_type: str
    fiscal_year: int
    scope_token: str
    consolidation_scope: str | None
    reference_date: date | None
    line_count: int
    general_corporate_critical_coverage: float
    general_corporate_total_coverage: float
    general_corporate_missing_critical: tuple[str, ...]
    general_corporate_missing_supporting: tuple[str, ...]
    holding_critical_schema_coverage: float
    holding_total_schema_coverage: float
    holding_exact_concepts: tuple[str, ...]
    holding_missing_concepts: tuple[str, ...]
    holding_label_mismatch_concepts: tuple[str, ...]
    holding_ambiguous_concepts: tuple[str, ...]
    total_assets: float | None
    investments_total: float | None
    equity: float | None
    revenue: float | None
    ebit: float | None
    equity_method_result: float | None
    net_income: float | None
    cash_from_operations: float | None
    investments_to_assets: float | None
    equity_to_assets: float | None
    equity_method_to_net_income: float | None
    source_documents: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class B100AccountingLifecycleReport:
    company_id: str
    snapshot_count: int
    evidence_snapshot_count: int
    latest_reference_date: date | None
    general_corporate_full_critical_snapshot_ids: tuple[str, ...]
    holding_full_critical_schema_snapshot_ids: tuple[str, ...]
    snapshots: tuple[B100AccountingSnapshot, ...]
    routing_ready: bool = False
    scoring_ready: bool = False
    applicability_registry_resolvable: bool = False
    scope: str = "DIAGNOSTIC_B100_ACCOUNTING_LIFECYCLE"
    effect: str = "diagnostic_only_no_scoring_or_routing"
    point_in_time_eligible: bool = False

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def audit_b100_accounting_lifecycle(
    snapshots: dict[tuple[str, int, str], list[FinancialStatementLine]],
) -> B100AccountingLifecycleReport:
    """Compare B100 accounting semantics across annual/interim and ind/con scopes.

    The audit does not choose a structural model. It separately measures ordinary
    corporate fixed-account coverage and compatibility with the already validated ITSA
    holding account schema so lifecycle/scope changes remain visible instead of being
    collapsed into one inferred business-model label.
    """

    audited = tuple(
        _audit_snapshot(document_type, fiscal_year, scope_token, lines)
        for (document_type, fiscal_year, scope_token), lines in snapshots.items()
    )
    evidence = tuple(item for item in audited if item.reference_date is not None)
    latest_reference = max(
        (item.reference_date for item in evidence if item.reference_date is not None),
        default=None,
    )
    general_full = tuple(
        item.snapshot_id
        for item in evidence
        if item.general_corporate_critical_coverage == 1.0
    )
    holding_full = tuple(
        item.snapshot_id
        for item in evidence
        if item.holding_critical_schema_coverage == 1.0
    )
    return B100AccountingLifecycleReport(
        company_id=B100_COMPANY_ID,
        snapshot_count=len(audited),
        evidence_snapshot_count=len(evidence),
        latest_reference_date=latest_reference,
        general_corporate_full_critical_snapshot_ids=general_full,
        holding_full_critical_schema_snapshot_ids=holding_full,
        snapshots=audited,
    )


def _audit_snapshot(
    document_type: str,
    fiscal_year: int,
    scope_token: str,
    lines: list[FinancialStatementLine],
) -> B100AccountingSnapshot:
    for line in lines:
        if line.company_id != B100_COMPANY_ID:
            raise ValueError(
                "B100 lifecycle audit company identity mismatch: "
                f"expected={B100_COMPANY_ID} actual={line.company_id}"
            )

    reference_date = max((line.reference_date for line in lines), default=None)
    current_lines = (
        [line for line in lines if line.reference_date == reference_date]
        if reference_date is not None
        else []
    )
    extraction = (
        extract_fixed_accounts(
            current_lines,
            company_id=B100_COMPANY_ID,
            reference_date=reference_date,
            consolidation_scope=None,
        )
        if reference_date is not None
        else None
    )
    values = extraction.values if extraction is not None else {}
    coverage = evaluate_contract(values, GENERAL_CORPORATE_CONTRACT)

    tree = audit_financial_statement_tree(
        current_lines,
        company_id=B100_COMPANY_ID,
        statements=("BPA", "BPP", "DRE"),
        max_depth=6,
    )
    holding_schema = compare_itsa_holding_schema(tree)

    total_assets = values.get("total_assets")
    investments_total = _tree_exact_value(tree, "BPA", "1.02.02")
    equity = values.get("equity")
    revenue = values.get("revenue")
    ebit = values.get("ebit")
    equity_method_result = _tree_exact_value(tree, "DRE", "3.04.06")
    net_income = values.get("net_income_parent")
    if net_income is None:
        net_income = values.get("net_income_consolidated")
    cash_from_operations = values.get("cash_from_operations")

    consolidation_scopes = tuple(
        sorted(
            {
                str(line.consolidation_scope)
                for line in current_lines
                if line.consolidation_scope is not None
            }
        )
    )
    source_documents = tuple(
        sorted(
            {
                str(line.source_document)
                for line in current_lines
                if line.source_document
            }
        )
    )
    snapshot_id = f"{document_type.upper()}_{fiscal_year}_{scope_token.lower()}"
    return B100AccountingSnapshot(
        snapshot_id=snapshot_id,
        document_type=document_type.upper(),
        fiscal_year=fiscal_year,
        scope_token=scope_token.lower(),
        consolidation_scope=(
            consolidation_scopes[0]
            if len(consolidation_scopes) == 1
            else " | ".join(consolidation_scopes) if consolidation_scopes else None
        ),
        reference_date=reference_date,
        line_count=len(current_lines),
        general_corporate_critical_coverage=coverage.critical_coverage,
        general_corporate_total_coverage=coverage.total_coverage,
        general_corporate_missing_critical=coverage.missing_critical,
        general_corporate_missing_supporting=coverage.missing_supporting,
        holding_critical_schema_coverage=holding_schema.critical_schema_coverage,
        holding_total_schema_coverage=holding_schema.total_schema_coverage,
        holding_exact_concepts=holding_schema.exact_concepts,
        holding_missing_concepts=holding_schema.missing_concepts,
        holding_label_mismatch_concepts=holding_schema.label_mismatch_concepts,
        holding_ambiguous_concepts=holding_schema.ambiguous_concepts,
        total_assets=total_assets,
        investments_total=investments_total,
        equity=equity,
        revenue=revenue,
        ebit=ebit,
        equity_method_result=equity_method_result,
        net_income=net_income,
        cash_from_operations=cash_from_operations,
        investments_to_assets=safe_div(investments_total, total_assets),
        equity_to_assets=safe_div(equity, total_assets),
        equity_method_to_net_income=safe_div(equity_method_result, net_income),
        source_documents=source_documents,
    )


def _tree_exact_value(tree, statement: str, account_code: str) -> float | None:
    matches = [
        line
        for line in tree.lines
        if line.statement == statement and line.account_code == account_code
    ]
    if len(matches) > 1:
        raise ValueError(
            "ambiguous B100 lifecycle exact account after tree normalization: "
            f"statement={statement} account_code={account_code} matches={len(matches)}"
        )
    return matches[0].value_brl if matches else None
