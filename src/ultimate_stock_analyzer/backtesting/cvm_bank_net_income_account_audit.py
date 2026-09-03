from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from datetime import date
from typing import Any

from ultimate_stock_analyzer.domain.master import FinancialStatementLine

CVM_BANK_NET_INCOME_ACCOUNT_UNPROVEN = "CVM_BANK_NET_INCOME_ACCOUNT_UNPROVEN"
CVM_BANK_FIXED_311_NOT_OBSERVED = "CVM_BANK_FIXED_311_NOT_OBSERVED"

_NET_INCOME_TOKENS = (
    "lucro liquido",
    "prejuizo",
    "resultado liquido",
    "resultado do periodo",
    "resultado atribuivel",
)


@dataclass(frozen=True, slots=True)
class CVMBankDREAccountObservation:
    account_code: str
    account_name: str
    value_brl: float
    fiscal_order: str | None
    consolidation_scope: str | None
    version: int
    available_from: str | None
    source_document: str | None
    heuristic_net_income_candidate: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "account_code": self.account_code,
            "account_name": self.account_name,
            "value_brl": self.value_brl,
            "fiscal_order": self.fiscal_order,
            "consolidation_scope": self.consolidation_scope,
            "version": self.version,
            "available_from": self.available_from,
            "source_document": self.source_document,
            "heuristic_net_income_candidate": self.heuristic_net_income_candidate,
        }


@dataclass(frozen=True, slots=True)
class CVMBankNetIncomeAccountAudit:
    company_id: str
    fiscal_year: int
    reference_date: date
    dre_line_count: int
    fixed_311_observed: bool
    fixed_311_rows: tuple[CVMBankDREAccountObservation, ...]
    heuristic_candidates: tuple[CVMBankDREAccountObservation, ...]
    dre_accounts: tuple[CVMBankDREAccountObservation, ...]
    blockers: tuple[str, ...]
    mapping_proven: bool = False
    readiness_promotion_allowed: bool = False
    schema_version: str = "0.1"

    @property
    def effect(self) -> str:
        return "diagnostic_only_cvm_bank_net_income_account_mapping"

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "effect": self.effect,
            "company_id": self.company_id,
            "fiscal_year": self.fiscal_year,
            "reference_date": self.reference_date.isoformat(),
            "dre_line_count": self.dre_line_count,
            "fixed_311_observed": self.fixed_311_observed,
            "fixed_311_rows": [item.to_dict() for item in self.fixed_311_rows],
            "heuristic_candidates": [
                item.to_dict() for item in self.heuristic_candidates
            ],
            "dre_accounts": [item.to_dict() for item in self.dre_accounts],
            "blockers": list(self.blockers),
            "mapping_proven": self.mapping_proven,
            "readiness_promotion_allowed": self.readiness_promotion_allowed,
        }


def audit_cvm_bank_net_income_accounts(
    lines: list[FinancialStatementLine],
    *,
    cvm_code: int,
    fiscal_year: int,
) -> CVMBankNetIncomeAccountAudit:
    reference_date = date(fiscal_year, 12, 31)
    selected = [
        line
        for line in lines
        if line.cvm_code == cvm_code
        and line.statement == "DRE"
        and line.reference_date == reference_date
        and line.fiscal_order == "ÚLTIMO"
    ]
    observations = tuple(
        sorted(
            (_observation(line) for line in selected),
            key=lambda item: (item.account_code, item.account_name, item.version),
        )
    )
    fixed_311 = tuple(item for item in observations if item.account_code == "3.11")
    heuristic = tuple(
        item for item in observations if item.heuristic_net_income_candidate
    )
    blockers = {CVM_BANK_NET_INCOME_ACCOUNT_UNPROVEN}
    if not fixed_311:
        blockers.add(CVM_BANK_FIXED_311_NOT_OBSERVED)

    return CVMBankNetIncomeAccountAudit(
        company_id=f"cvm:{cvm_code}",
        fiscal_year=fiscal_year,
        reference_date=reference_date,
        dre_line_count=len(observations),
        fixed_311_observed=bool(fixed_311),
        fixed_311_rows=fixed_311,
        heuristic_candidates=heuristic,
        dre_accounts=observations,
        blockers=tuple(sorted(blockers)),
    )


def _observation(line: FinancialStatementLine) -> CVMBankDREAccountObservation:
    return CVMBankDREAccountObservation(
        account_code=line.account_code,
        account_name=line.account_name,
        value_brl=line.value_brl,
        fiscal_order=line.fiscal_order,
        consolidation_scope=line.consolidation_scope,
        version=line.version,
        available_from=(
            line.available_from.isoformat() if line.available_from is not None else None
        ),
        source_document=line.source_document,
        heuristic_net_income_candidate=_looks_like_net_income(line.account_name),
    )


def _looks_like_net_income(account_name: str) -> bool:
    normalized = _normalize_label(account_name)
    return any(token in normalized for token in _NET_INCOME_TOKENS)


def _normalize_label(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value.casefold())
    without_marks = "".join(
        character for character in decomposed if not unicodedata.combining(character)
    )
    return " ".join(without_marks.split())
