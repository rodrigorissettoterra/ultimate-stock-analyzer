from __future__ import annotations

import unicodedata
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import date

from ultimate_stock_analyzer.domain.master import FinancialStatementLine
from ultimate_stock_analyzer.fundamentals.metrics import safe_div


@dataclass(frozen=True, slots=True, order=True)
class HoldingAccountCandidate:
    company_id: str
    statement: str
    account_code: str
    account_name: str
    value_brl: float
    reference_date: date
    consolidation_scope: str | None
    document_type: str


@dataclass(frozen=True, slots=True)
class HoldingCompanyDataAudit:
    company_id: str
    reference_date: date | None
    total_assets: float | None
    equity: float | None
    net_income_parent: float | None
    cash_and_current_financial_investments: float | None
    gross_borrowings: float | None
    investment_candidates_total: float | None
    equity_method_candidates_total: float | None
    investments_to_assets: float | None
    equity_method_to_net_income: float | None
    candidate_accounts: tuple[HoldingAccountCandidate, ...]
    warnings: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class HoldingModelDataContractAuditReport:
    company_ids: tuple[str, ...]
    company_audits: tuple[HoldingCompanyDataAudit, ...]
    scope: str = "DIAGNOSTIC_HOLDING_MODEL_DATA_CONTRACT"
    effect: str = "diagnostic_only"
    point_in_time_eligible: bool = False

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def audit_holding_model_data_contract(
    lines: list[FinancialStatementLine],
    *,
    company_ids: tuple[str, ...],
) -> HoldingModelDataContractAuditReport:
    """Inspect holding-specific CVM account evidence without defining score mappings.

    Candidate account discovery uses normalized account descriptions only to expose
    rows for human/model-contract review. It does not establish issuer identity,
    score values, sector routing, or a normative account mapping.
    """

    grouped: dict[str, list[FinancialStatementLine]] = defaultdict(list)
    for line in lines:
        if line.company_id in company_ids:
            grouped[line.company_id].append(line)

    audits = tuple(
        _audit_company(company_id, grouped.get(company_id, []))
        for company_id in sorted(company_ids)
    )
    return HoldingModelDataContractAuditReport(
        company_ids=tuple(sorted(company_ids)),
        company_audits=audits,
    )


def _audit_company(
    company_id: str,
    lines: list[FinancialStatementLine],
) -> HoldingCompanyDataAudit:
    latest_reference = max((line.reference_date for line in lines), default=None)
    current = [
        line
        for line in lines
        if latest_reference is not None
        and line.reference_date == latest_reference
        and line.fiscal_order == "ÚLTIMO"
    ]

    candidates = tuple(
        sorted(
            HoldingAccountCandidate(
                company_id=line.company_id,
                statement=line.statement,
                account_code=line.account_code,
                account_name=line.account_name,
                value_brl=line.value_brl,
                reference_date=line.reference_date,
                consolidation_scope=line.consolidation_scope,
                document_type=line.document_type,
            )
            for line in current
            if _is_holding_candidate(line)
        )
    )

    total_assets = _exact_value(current, statement="BPA", account_code="1")
    equity = _exact_value(current, statement="BPP", account_code="2.03")
    net_income_parent = _exact_value(current, statement="DRE", account_code="3.11.01")
    if net_income_parent is None:
        net_income_parent = _exact_value(current, statement="DRE", account_code="3.11")

    cash = _exact_value(current, statement="BPA", account_code="1.01.01")
    current_investments = _exact_value(current, statement="BPA", account_code="1.01.02")
    liquid_funds = _sum_known(cash, current_investments)
    borrowings = _sum_known(
        _exact_value(current, statement="BPP", account_code="2.01.04"),
        _exact_value(current, statement="BPP", account_code="2.02.01"),
    )

    investment_candidates = [
        item.value_brl
        for item in candidates
        if item.statement == "BPA" and _is_investment_name(item.account_name)
    ]
    equity_method_candidates = [
        item.value_brl
        for item in candidates
        if item.statement == "DRE" and _is_equity_method_name(item.account_name)
    ]
    investment_total = _candidate_total(investment_candidates)
    equity_method_total = _candidate_total(equity_method_candidates)

    warnings: list[str] = []
    if not lines:
        warnings.append("NO_DFP_LINES_FOR_COMPANY")
    if not investment_candidates:
        warnings.append("NO_INVESTMENT_ACCOUNT_CANDIDATE")
    if not equity_method_candidates:
        warnings.append("NO_EQUITY_METHOD_ACCOUNT_CANDIDATE")
    if len(investment_candidates) > 1:
        warnings.append("MULTIPLE_INVESTMENT_ACCOUNT_CANDIDATES")
    if len(equity_method_candidates) > 1:
        warnings.append("MULTIPLE_EQUITY_METHOD_ACCOUNT_CANDIDATES")

    return HoldingCompanyDataAudit(
        company_id=company_id,
        reference_date=latest_reference,
        total_assets=total_assets,
        equity=equity,
        net_income_parent=net_income_parent,
        cash_and_current_financial_investments=liquid_funds,
        gross_borrowings=borrowings,
        investment_candidates_total=investment_total,
        equity_method_candidates_total=equity_method_total,
        investments_to_assets=safe_div(investment_total, total_assets),
        equity_method_to_net_income=safe_div(equity_method_total, net_income_parent),
        candidate_accounts=candidates,
        warnings=tuple(sorted(warnings)),
    )


def _exact_value(
    lines: list[FinancialStatementLine],
    *,
    statement: str,
    account_code: str,
) -> float | None:
    matches = [
        line
        for line in lines
        if line.statement == statement and line.account_code == account_code
    ]
    if not matches:
        return None
    selected = max(matches, key=lambda line: (line.version, line.document_id or -1))
    return selected.value_brl


def _is_holding_candidate(line: FinancialStatementLine) -> bool:
    if line.statement == "BPA" and _is_investment_name(line.account_name):
        return True
    return line.statement == "DRE" and _is_equity_method_name(line.account_name)


def _is_investment_name(value: str) -> bool:
    text = _normalized_text(value)
    return any(
        token in text
        for token in (
            "investimentos",
            "participacoes societarias",
            "participacao societaria",
            "investimento em controladas",
            "investimentos em controladas",
            "investimento em coligadas",
            "investimentos em coligadas",
        )
    )


def _is_equity_method_name(value: str) -> bool:
    text = _normalized_text(value)
    return "equivalencia patrimonial" in text


def _normalized_text(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", str(value))
    return " ".join(
        "".join(char for char in decomposed if not unicodedata.combining(char))
        .lower()
        .split()
    )


def _sum_known(*values: float | None) -> float | None:
    known = [value for value in values if value is not None]
    return sum(known) if known else None


def _candidate_total(values: list[float]) -> float | None:
    if not values:
        return None
    # Candidate totals are diagnostic only. Avoid double counting nested account trees:
    # when multiple matches exist, expose them all and withhold the aggregate.
    if len(values) != 1:
        return None
    return values[0]
