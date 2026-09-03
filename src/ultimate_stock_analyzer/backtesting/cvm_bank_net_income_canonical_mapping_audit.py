from __future__ import annotations

import math
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from ultimate_stock_analyzer.domain.master import FinancialStatementLine

CVM_BANK_NET_INCOME_ACCOUNT_309_MISSING = "CVM_BANK_NET_INCOME_ACCOUNT_309_MISSING"
CVM_BANK_NET_INCOME_ACCOUNT_309_LABEL_MISMATCH = (
    "CVM_BANK_NET_INCOME_ACCOUNT_309_LABEL_MISMATCH"
)
CVM_BANK_NET_INCOME_CONTINUITY_IDENTITY_FAILED = (
    "CVM_BANK_NET_INCOME_CONTINUITY_IDENTITY_FAILED"
)
CVM_BANK_NET_INCOME_AVAILABILITY_MISSING = (
    "CVM_BANK_NET_INCOME_AVAILABILITY_MISSING"
)
CVM_BANK_NET_INCOME_DUPLICATE_ACCOUNT_CODE = (
    "CVM_BANK_NET_INCOME_DUPLICATE_ACCOUNT_CODE"
)
CVM_BANK_NET_INCOME_MAPPING_WINDOW_INCOMPLETE = (
    "CVM_BANK_NET_INCOME_MAPPING_WINDOW_INCOMPLETE"
)
CVM_BANK_DFP_REVISION_HISTORY_COMPLETENESS_UNPROVEN = (
    "CVM_BANK_DFP_REVISION_HISTORY_COMPLETENESS_UNPROVEN"
)
CVM_BANK_DFP_PRUDENTIAL_SCOPE_ALIGNMENT_UNPROVEN = (
    "CVM_BANK_DFP_PRUDENTIAL_SCOPE_ALIGNMENT_UNPROVEN"
)

_EXPECTED_309_LABEL = "lucro/prejuizo consolidado do periodo"
_ARITHMETIC_ABS_TOLERANCE_BRL = 1_000.0


@dataclass(frozen=True, slots=True)
class CVMBankNetIncomeAccountValue:
    account_code: str
    account_name: str
    value_brl: float
    available_from: datetime | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "account_code": self.account_code,
            "account_name": self.account_name,
            "value_brl": self.value_brl,
            "available_from": (
                self.available_from.isoformat()
                if self.available_from is not None
                else None
            ),
        }


@dataclass(frozen=True, slots=True)
class CVMBankNetIncomeVersionValidation:
    fiscal_year: int
    version: int
    row_count: int
    account_307: CVMBankNetIncomeAccountValue | None
    account_308: CVMBankNetIncomeAccountValue | None
    account_309: CVMBankNetIncomeAccountValue | None
    account_30901: CVMBankNetIncomeAccountValue | None
    account_30902: CVMBankNetIncomeAccountValue | None
    duplicate_account_codes: tuple[str, ...]
    account_309_label_validated: bool
    continuity_identity_validated: bool
    attribution_identity_validated: bool | None
    availability_timestamp_validated: bool
    observed_mapping_validated: bool
    blockers: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "fiscal_year": self.fiscal_year,
            "version": self.version,
            "row_count": self.row_count,
            "account_307": _account_dict(self.account_307),
            "account_308": _account_dict(self.account_308),
            "account_309": _account_dict(self.account_309),
            "account_30901": _account_dict(self.account_30901),
            "account_30902": _account_dict(self.account_30902),
            "duplicate_account_codes": list(self.duplicate_account_codes),
            "account_309_label_validated": self.account_309_label_validated,
            "continuity_identity_validated": self.continuity_identity_validated,
            "attribution_identity_validated": self.attribution_identity_validated,
            "availability_timestamp_validated": self.availability_timestamp_validated,
            "observed_mapping_validated": self.observed_mapping_validated,
            "blockers": list(self.blockers),
        }


@dataclass(frozen=True, slots=True)
class CVMBankNetIncomeCanonicalMappingAudit:
    company_id: str
    requested_years: tuple[int, ...]
    observed_years: tuple[int, ...]
    versions: tuple[CVMBankNetIncomeVersionValidation, ...]
    canonical_account_code: str | None
    canonical_account_label: str | None
    canonical_mapping_supported_for_observed_scope: bool
    revision_history_completeness_proven: bool
    prudential_scope_alignment_proven: bool
    bank_evidence_point_in_time_ready: bool
    readiness_promotion_allowed: bool
    blockers: tuple[str, ...]
    schema_version: str = "0.1"

    @property
    def effect(self) -> str:
        return "validate_cvm_bank_net_income_mapping_no_bank_readiness_change"

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "effect": self.effect,
            "company_id": self.company_id,
            "requested_years": list(self.requested_years),
            "observed_years": list(self.observed_years),
            "versions": [item.to_dict() for item in self.versions],
            "canonical_account_code": self.canonical_account_code,
            "canonical_account_label": self.canonical_account_label,
            "canonical_mapping_supported_for_observed_scope": (
                self.canonical_mapping_supported_for_observed_scope
            ),
            "revision_history_completeness_proven": (
                self.revision_history_completeness_proven
            ),
            "prudential_scope_alignment_proven": self.prudential_scope_alignment_proven,
            "bank_evidence_point_in_time_ready": self.bank_evidence_point_in_time_ready,
            "readiness_promotion_allowed": self.readiness_promotion_allowed,
            "blockers": list(self.blockers),
        }


def audit_cvm_bank_net_income_canonical_mapping(
    lines: list[FinancialStatementLine],
    *,
    cvm_code: int,
    years: tuple[int, ...],
) -> CVMBankNetIncomeCanonicalMappingAudit:
    requested_years = tuple(sorted(set(years)))
    selected = [
        line
        for line in lines
        if line.cvm_code == cvm_code
        and line.statement == "DRE"
        and line.fiscal_order == "ÚLTIMO"
        and line.reference_date.year in requested_years
        and line.reference_date.month == 12
        and line.reference_date.day == 31
    ]
    observed_years = tuple(sorted({line.reference_date.year for line in selected}))
    grouped: dict[tuple[int, int], list[FinancialStatementLine]] = {}
    for line in selected:
        grouped.setdefault((line.reference_date.year, line.version), []).append(line)

    validations = tuple(
        _validate_version(fiscal_year=year, version=version, lines=version_lines)
        for (year, version), version_lines in sorted(grouped.items())
    )
    mapping_supported = (
        observed_years == requested_years
        and bool(validations)
        and all(item.observed_mapping_validated for item in validations)
    )

    blockers = {
        CVM_BANK_DFP_REVISION_HISTORY_COMPLETENESS_UNPROVEN,
        CVM_BANK_DFP_PRUDENTIAL_SCOPE_ALIGNMENT_UNPROVEN,
    }
    if observed_years != requested_years:
        blockers.add(CVM_BANK_NET_INCOME_MAPPING_WINDOW_INCOMPLETE)
    for validation in validations:
        blockers.update(validation.blockers)

    return CVMBankNetIncomeCanonicalMappingAudit(
        company_id=f"cvm:{cvm_code}",
        requested_years=requested_years,
        observed_years=observed_years,
        versions=validations,
        canonical_account_code="3.09" if mapping_supported else None,
        canonical_account_label=(
            "Lucro/Prejuízo Consolidado do Período" if mapping_supported else None
        ),
        canonical_mapping_supported_for_observed_scope=mapping_supported,
        revision_history_completeness_proven=False,
        prudential_scope_alignment_proven=False,
        bank_evidence_point_in_time_ready=False,
        readiness_promotion_allowed=False,
        blockers=tuple(sorted(blockers)),
    )


def _validate_version(
    *,
    fiscal_year: int,
    version: int,
    lines: list[FinancialStatementLine],
) -> CVMBankNetIncomeVersionValidation:
    by_code: dict[str, list[FinancialStatementLine]] = {}
    for line in lines:
        by_code.setdefault(line.account_code, []).append(line)
    duplicates = tuple(sorted(code for code, rows in by_code.items() if len(rows) != 1))

    account_307 = _single_account(by_code, "3.07")
    account_308 = _single_account(by_code, "3.08")
    account_309 = _single_account(by_code, "3.09")
    account_30901 = _single_account(by_code, "3.09.01")
    account_30902 = _single_account(by_code, "3.09.02")

    label_validated = (
        account_309 is not None
        and _normalize_label(account_309.account_name) == _EXPECTED_309_LABEL
    )
    continuity_validated = _sum_identity(account_309, account_307, account_308)
    attribution_validated = _optional_sum_identity(
        account_309,
        account_30901,
        account_30902,
    )
    availability_validated = (
        account_309 is not None and account_309.available_from is not None
    )

    blockers: set[str] = set()
    if duplicates:
        blockers.add(CVM_BANK_NET_INCOME_DUPLICATE_ACCOUNT_CODE)
    if account_309 is None:
        blockers.add(CVM_BANK_NET_INCOME_ACCOUNT_309_MISSING)
    elif not label_validated:
        blockers.add(CVM_BANK_NET_INCOME_ACCOUNT_309_LABEL_MISMATCH)
    if not continuity_validated:
        blockers.add(CVM_BANK_NET_INCOME_CONTINUITY_IDENTITY_FAILED)
    if not availability_validated:
        blockers.add(CVM_BANK_NET_INCOME_AVAILABILITY_MISSING)

    validated = (
        not duplicates
        and account_309 is not None
        and label_validated
        and continuity_validated
        and availability_validated
    )
    return CVMBankNetIncomeVersionValidation(
        fiscal_year=fiscal_year,
        version=version,
        row_count=len(lines),
        account_307=account_307,
        account_308=account_308,
        account_309=account_309,
        account_30901=account_30901,
        account_30902=account_30902,
        duplicate_account_codes=duplicates,
        account_309_label_validated=label_validated,
        continuity_identity_validated=continuity_validated,
        attribution_identity_validated=attribution_validated,
        availability_timestamp_validated=availability_validated,
        observed_mapping_validated=validated,
        blockers=tuple(sorted(blockers)),
    )


def _single_account(
    by_code: dict[str, list[FinancialStatementLine]],
    code: str,
) -> CVMBankNetIncomeAccountValue | None:
    rows = by_code.get(code, [])
    if len(rows) != 1:
        return None
    line = rows[0]
    return CVMBankNetIncomeAccountValue(
        account_code=line.account_code,
        account_name=line.account_name,
        value_brl=line.value_brl,
        available_from=line.available_from,
    )


def _sum_identity(
    total: CVMBankNetIncomeAccountValue | None,
    left: CVMBankNetIncomeAccountValue | None,
    right: CVMBankNetIncomeAccountValue | None,
) -> bool:
    if total is None or left is None or right is None:
        return False
    return math.isclose(
        total.value_brl,
        left.value_brl + right.value_brl,
        rel_tol=1e-9,
        abs_tol=_ARITHMETIC_ABS_TOLERANCE_BRL,
    )


def _optional_sum_identity(
    total: CVMBankNetIncomeAccountValue | None,
    left: CVMBankNetIncomeAccountValue | None,
    right: CVMBankNetIncomeAccountValue | None,
) -> bool | None:
    if left is None and right is None:
        return None
    if total is None or left is None or right is None:
        return False
    return _sum_identity(total, left, right)


def _normalize_label(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value.casefold())
    without_marks = "".join(
        character for character in decomposed if not unicodedata.combining(character)
    )
    return " ".join(without_marks.split())


def _account_dict(
    value: CVMBankNetIncomeAccountValue | None,
) -> dict[str, Any] | None:
    return value.to_dict() if value is not None else None
