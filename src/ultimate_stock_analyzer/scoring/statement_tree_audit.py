from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date

from ultimate_stock_analyzer.domain.master import FinancialStatementLine


@dataclass(frozen=True, slots=True, order=True)
class StatementTreeLine:
    statement: str
    account_code: str
    account_name: str
    value_brl: float
    depth: int
    consolidation_scope: str | None
    document_type: str
    version: int
    document_id: int | None


@dataclass(frozen=True, slots=True)
class FinancialStatementTreeAuditReport:
    company_id: str
    reference_date: date | None
    max_depth: int
    statement_counts: dict[str, int]
    lines: tuple[StatementTreeLine, ...]
    scope: str = "DIAGNOSTIC_CVM_FINANCIAL_STATEMENT_TREE"
    effect: str = "diagnostic_only"
    point_in_time_eligible: bool = False

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def audit_financial_statement_tree(
    lines: list[FinancialStatementLine],
    *,
    company_id: str,
    statements: tuple[str, ...] = ("BPA", "BPP", "DRE"),
    max_depth: int = 4,
) -> FinancialStatementTreeAuditReport:
    """Expose a bounded latest CVM account tree without defining semantic mappings."""

    if max_depth < 1:
        raise ValueError("max_depth must be at least 1")

    candidate_lines = [
        line
        for line in lines
        if line.company_id == company_id and line.statement in statements
    ]
    latest_reference = max(
        (line.reference_date for line in candidate_lines),
        default=None,
    )
    if latest_reference is None:
        return FinancialStatementTreeAuditReport(
            company_id=company_id,
            reference_date=None,
            max_depth=max_depth,
            statement_counts={},
            lines=(),
        )

    winners: dict[
        tuple[str, str, str | None],
        FinancialStatementLine,
    ] = {}
    for line in candidate_lines:
        if line.reference_date != latest_reference or line.fiscal_order != "ÚLTIMO":
            continue
        key = (line.statement, line.account_code, line.consolidation_scope)
        current = winners.get(key)
        if current is None or _revision_rank(line) > _revision_rank(current):
            winners[key] = line

    tree_lines = tuple(
        sorted(
            StatementTreeLine(
                statement=line.statement,
                account_code=line.account_code,
                account_name=line.account_name,
                value_brl=line.value_brl,
                depth=_account_depth(line.account_code),
                consolidation_scope=line.consolidation_scope,
                document_type=line.document_type,
                version=line.version,
                document_id=line.document_id,
            )
            for line in winners.values()
            if _account_depth(line.account_code) <= max_depth
        )
    )
    counts = {
        statement: sum(1 for line in tree_lines if line.statement == statement)
        for statement in statements
        if any(line.statement == statement for line in tree_lines)
    }

    return FinancialStatementTreeAuditReport(
        company_id=company_id,
        reference_date=latest_reference,
        max_depth=max_depth,
        statement_counts=counts,
        lines=tree_lines,
    )


def _account_depth(account_code: str) -> int:
    return len([part for part in str(account_code).split(".") if part])


def _revision_rank(line: FinancialStatementLine) -> tuple[int, int]:
    return line.version, line.document_id or -1
