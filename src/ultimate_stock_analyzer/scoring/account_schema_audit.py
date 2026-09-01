from __future__ import annotations

import unicodedata
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import date
from typing import Literal

from ultimate_stock_analyzer.domain.master import FinancialStatementLine
from ultimate_stock_analyzer.fundamentals.cvm_accounts import (
    GENERAL_CORPORATE_FIXED_ACCOUNTS,
)

AccountSchemaStatus = Literal[
    "CONSISTENT_ACCOUNT_LABEL",
    "DIVERGENT_ACCOUNT_LABEL",
    "PARTIAL_COVERAGE",
    "MISSING_ALL",
]


@dataclass(frozen=True, slots=True, order=True)
class AccountSchemaObservation:
    company_id: str
    concept_name: str
    statement: str
    account_code: str
    account_name: str
    normalized_account_name: str
    value_brl: float
    reference_date: date
    consolidation_scope: str | None
    document_type: str


@dataclass(frozen=True, slots=True)
class AccountConceptSchemaAudit:
    concept_name: str
    statements: tuple[str, ...]
    account_code: str
    status: AccountSchemaStatus
    company_count: int
    observed_company_count: int
    missing_company_ids: tuple[str, ...]
    observed_account_names: tuple[str, ...]
    normalized_account_names: tuple[str, ...]
    observations: tuple[AccountSchemaObservation, ...]


@dataclass(frozen=True, slots=True)
class GeneralCorporateAccountSchemaAuditReport:
    company_ids: tuple[str, ...]
    concepts: tuple[AccountConceptSchemaAudit, ...]
    divergent_concepts: tuple[str, ...]
    partial_coverage_concepts: tuple[str, ...]
    missing_all_concepts: tuple[str, ...]
    scope: str = "DIAGNOSTIC_GENERAL_CORPORATE_ACCOUNT_SCHEMA"
    effect: str = "diagnostic_only"
    point_in_time_eligible: bool = False

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def audit_general_corporate_account_schema(
    lines: list[FinancialStatementLine],
    *,
    company_ids: tuple[str, ...],
) -> GeneralCorporateAccountSchemaAuditReport:
    """Compare exact CVM account-code labels across canonical companies.

    The audit intentionally does not decide whether two different labels are
    economically equivalent. Divergent official labels are surfaced for review
    instead of being silently treated as one normalized scoring concept.
    """

    normalized_company_ids = tuple(sorted(set(company_ids)))
    latest_reference_by_company = _latest_reference_dates(
        lines,
        normalized_company_ids,
    )
    current = _latest_rows(
        lines,
        latest_reference_by_company=latest_reference_by_company,
    )

    concepts: list[AccountConceptSchemaAudit] = []
    for account in GENERAL_CORPORATE_FIXED_ACCOUNTS:
        if not set(account.statements).intersection({"BPA", "BPP", "DRE"}):
            continue
        observations = _concept_observations(
            current,
            company_ids=normalized_company_ids,
            concept_name=account.name,
            statements=account.statements,
            account_code=account.code,
        )
        observed_ids = {item.company_id for item in observations}
        missing_ids = tuple(
            company_id
            for company_id in normalized_company_ids
            if company_id not in observed_ids
        )
        labels = tuple(sorted({item.account_name for item in observations}))
        normalized_labels = tuple(
            sorted({item.normalized_account_name for item in observations})
        )

        if not observations:
            status: AccountSchemaStatus = "MISSING_ALL"
        elif missing_ids:
            status = "PARTIAL_COVERAGE"
        elif len(normalized_labels) == 1:
            status = "CONSISTENT_ACCOUNT_LABEL"
        else:
            status = "DIVERGENT_ACCOUNT_LABEL"

        concepts.append(
            AccountConceptSchemaAudit(
                concept_name=account.name,
                statements=account.statements,
                account_code=account.code,
                status=status,
                company_count=len(normalized_company_ids),
                observed_company_count=len(observed_ids),
                missing_company_ids=missing_ids,
                observed_account_names=labels,
                normalized_account_names=normalized_labels,
                observations=tuple(sorted(observations)),
            )
        )

    return GeneralCorporateAccountSchemaAuditReport(
        company_ids=normalized_company_ids,
        concepts=tuple(concepts),
        divergent_concepts=tuple(
            item.concept_name
            for item in concepts
            if item.status == "DIVERGENT_ACCOUNT_LABEL"
        ),
        partial_coverage_concepts=tuple(
            item.concept_name
            for item in concepts
            if item.status == "PARTIAL_COVERAGE"
        ),
        missing_all_concepts=tuple(
            item.concept_name
            for item in concepts
            if item.status == "MISSING_ALL"
        ),
    )


def _latest_reference_dates(
    lines: list[FinancialStatementLine],
    company_ids: tuple[str, ...],
) -> dict[str, date]:
    grouped: dict[str, list[date]] = defaultdict(list)
    for line in lines:
        if line.company_id in company_ids:
            grouped[line.company_id].append(line.reference_date)
    return {
        company_id: max(reference_dates)
        for company_id, reference_dates in grouped.items()
        if reference_dates
    }


def _latest_rows(
    lines: list[FinancialStatementLine],
    *,
    latest_reference_by_company: dict[str, date],
) -> list[FinancialStatementLine]:
    winners: dict[
        tuple[str, str, str, str | None],
        FinancialStatementLine,
    ] = {}
    for line in lines:
        if line.fiscal_order != "ÚLTIMO":
            continue
        latest_reference = latest_reference_by_company.get(line.company_id)
        if latest_reference is None or line.reference_date != latest_reference:
            continue
        key = (
            line.company_id,
            line.statement,
            line.account_code,
            line.consolidation_scope,
        )
        current = winners.get(key)
        if current is None or _revision_rank(line) > _revision_rank(current):
            winners[key] = line
    return list(winners.values())


def _concept_observations(
    lines: list[FinancialStatementLine],
    *,
    company_ids: tuple[str, ...],
    concept_name: str,
    statements: tuple[str, ...],
    account_code: str,
) -> list[AccountSchemaObservation]:
    observations: list[AccountSchemaObservation] = []
    for company_id in company_ids:
        matches = [
            line
            for line in lines
            if line.company_id == company_id
            and line.statement in statements
            and line.account_code == account_code
        ]
        if not matches:
            continue
        selected = max(matches, key=_revision_rank)
        observations.append(
            AccountSchemaObservation(
                company_id=company_id,
                concept_name=concept_name,
                statement=selected.statement,
                account_code=selected.account_code,
                account_name=selected.account_name,
                normalized_account_name=_normalized_text(selected.account_name),
                value_brl=selected.value_brl,
                reference_date=selected.reference_date,
                consolidation_scope=selected.consolidation_scope,
                document_type=selected.document_type,
            )
        )
    return observations


def _revision_rank(line: FinancialStatementLine) -> tuple[int, int]:
    return line.version, line.document_id or -1


def _normalized_text(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", str(value))
    return " ".join(
        "".join(char for char in decomposed if not unicodedata.combining(char))
        .lower()
        .split()
    )
