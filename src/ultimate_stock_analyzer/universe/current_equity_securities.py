from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass
from datetime import date
from typing import Literal

from ultimate_stock_analyzer.universe.b3_current_security_audit import (
    B3CompanyCurrentSecurityEvidence,
    B3CurrentSecurityAuditReport,
    B3SecurityTradingEvidence,
)
from ultimate_stock_analyzer.universe.b3_security_types import (
    B3SecurityKind,
    classify_b3_security_specifications,
)
from ultimate_stock_analyzer.universe.eligibility import (
    BrazilianEquityEligibilityReport,
)

CurrentBrazilianEquitySecurityStatus = Literal[
    "ELIGIBLE_CURRENT_CORE_EQUITY_SECURITY",
    "EXCLUDED_NO_CURRENT_SPOT_TRADE",
    "EXCLUDED_NON_CORE_SECURITY_KIND",
    "EXCLUDED_UNKNOWN_SECURITY_KIND",
    "EXCLUDED_SECURITY_TAXONOMY_CONFLICT",
    "EXCLUDED_SECURITY_CODE_IDENTITY_CONFLICT",
]

CurrentBrazilianEquityCompanyStatus = Literal[
    "ELIGIBLE_CURRENT_BRAZILIAN_EQUITY",
    "EXCLUDED_ISSUER_NOT_ELIGIBLE",
    "EXCLUDED_DETAIL_UNAVAILABLE",
    "EXCLUDED_DETAIL_IDENTITY_CONFLICT",
    "EXCLUDED_SECURITY_CODE_IDENTITY_CONFLICT",
    "EXCLUDED_NO_CURRENT_CORE_EQUITY_SECURITY",
]


@dataclass(frozen=True, slots=True, order=True)
class CurrentBrazilianEquitySecurityDecision:
    company_id: str
    code: str
    status: CurrentBrazilianEquitySecurityStatus
    eligible: bool
    security_kind: str | None
    specifications: tuple[str, ...]
    trade_days: int
    first_trade_date: date | None
    last_trade_date: date | None
    detail_isin: str | None
    observed_isins: tuple[str, ...]
    reason: str


@dataclass(frozen=True, slots=True, order=True)
class CurrentBrazilianEquityCompanyDecision:
    company_id: str
    issuer_code: str
    trading_name: str
    issuer_status: str
    status: CurrentBrazilianEquityCompanyStatus
    eligible: bool
    exact_security_codes: tuple[str, ...]
    eligible_security_codes: tuple[str, ...]
    excluded_security_codes: tuple[str, ...]
    reason: str


@dataclass(frozen=True, slots=True)
class CurrentBrazilianEquitySecurityUniverseReport:
    candidate_company_ids: int
    eligible_company_count: int
    eligible_security_count: int
    company_status_counts: dict[str, int]
    security_status_counts: dict[str, int]
    eligible_company_ids: tuple[str, ...]
    eligible_security_codes: tuple[str, ...]
    company_decisions: tuple[CurrentBrazilianEquityCompanyDecision, ...]
    security_decisions: tuple[CurrentBrazilianEquitySecurityDecision, ...]
    scope: str = "CURRENT_BRAZILIAN_B3_CORE_EQUITY"
    point_in_time_eligible: bool = False

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def classify_current_brazilian_equity_securities(
    *,
    issuer_eligibility: BrazilianEquityEligibilityReport,
    security_audit: B3CurrentSecurityAuditReport,
) -> CurrentBrazilianEquitySecurityUniverseReport:
    issuer_decisions = {
        decision.company_id: decision for decision in issuer_eligibility.decisions
    }
    companies = {
        evidence.company_id: evidence for evidence in security_audit.company_evidence
    }
    if len(companies) != len(security_audit.company_evidence):
        raise ValueError("B3 current-security audit contains duplicate company_id values")

    missing_issuer_decisions = sorted(set(companies) - issuer_decisions.keys())
    if missing_issuer_decisions:
        raise ValueError(
            "B3 security universe lacks issuer eligibility decisions: "
            + ", ".join(missing_issuer_decisions[:10])
        )

    security_evidence = _security_evidence_index(security_audit.security_evidence)
    code_conflicts = security_audit.security_code_identity_conflicts

    company_decisions: list[CurrentBrazilianEquityCompanyDecision] = []
    security_decisions: list[CurrentBrazilianEquitySecurityDecision] = []

    for company_id, company in sorted(companies.items()):
        issuer = issuer_decisions[company_id]
        if not issuer.eligible:
            company_decisions.append(
                _company_decision(
                    company=company,
                    issuer_status=issuer.status,
                    status="EXCLUDED_ISSUER_NOT_ELIGIBLE",
                    eligible_security_codes=(),
                    excluded_security_codes=company.exact_security_codes,
                    reason=issuer.reason,
                )
            )
            continue

        if company.status == "DETAIL_UNAVAILABLE":
            company_decisions.append(
                _company_decision(
                    company=company,
                    issuer_status=issuer.status,
                    status="EXCLUDED_DETAIL_UNAVAILABLE",
                    eligible_security_codes=(),
                    excluded_security_codes=company.exact_security_codes,
                    reason=company.reason,
                )
            )
            continue
        if company.status == "DETAIL_IDENTITY_CONFLICT":
            company_decisions.append(
                _company_decision(
                    company=company,
                    issuer_status=issuer.status,
                    status="EXCLUDED_DETAIL_IDENTITY_CONFLICT",
                    eligible_security_codes=(),
                    excluded_security_codes=company.exact_security_codes,
                    reason=company.reason,
                )
            )
            continue
        if company.status == "SECURITY_CODE_IDENTITY_CONFLICT":
            company_decisions.append(
                _company_decision(
                    company=company,
                    issuer_status=issuer.status,
                    status="EXCLUDED_SECURITY_CODE_IDENTITY_CONFLICT",
                    eligible_security_codes=(),
                    excluded_security_codes=company.exact_security_codes,
                    reason=company.reason,
                )
            )
            continue

        decisions = [
            _classify_security(
                company_id=company_id,
                code=code,
                evidence=security_evidence.get((company_id, code)),
                code_conflict=code in code_conflicts,
            )
            for code in company.exact_security_codes
        ]
        security_decisions.extend(decisions)
        eligible_codes = tuple(sorted(item.code for item in decisions if item.eligible))
        excluded_codes = tuple(sorted(item.code for item in decisions if not item.eligible))

        if eligible_codes:
            company_status: CurrentBrazilianEquityCompanyStatus = (
                "ELIGIBLE_CURRENT_BRAZILIAN_EQUITY"
            )
            reason = (
                "The issuer is an eligible Brazilian public company and at least one exact "
                "B3 security code has current-year spot-market evidence with a coherent "
                "core-equity ESPECI classification."
            )
        else:
            company_status = "EXCLUDED_NO_CURRENT_CORE_EQUITY_SECURITY"
            reason = (
                "No exact B3 security code for this eligible Brazilian issuer has both "
                "current-year spot-market evidence and a coherent core-equity ESPECI "
                "classification."
            )

        company_decisions.append(
            _company_decision(
                company=company,
                issuer_status=issuer.status,
                status=company_status,
                eligible_security_codes=eligible_codes,
                excluded_security_codes=excluded_codes,
                reason=reason,
            )
        )

    company_counts = Counter(item.status for item in company_decisions)
    security_counts = Counter(item.status for item in security_decisions)
    eligible_company_ids = tuple(
        item.company_id for item in company_decisions if item.eligible
    )
    eligible_security_codes = tuple(
        sorted(item.code for item in security_decisions if item.eligible)
    )

    return CurrentBrazilianEquitySecurityUniverseReport(
        candidate_company_ids=len(company_decisions),
        eligible_company_count=len(eligible_company_ids),
        eligible_security_count=len(eligible_security_codes),
        company_status_counts=dict(sorted(company_counts.items())),
        security_status_counts=dict(sorted(security_counts.items())),
        eligible_company_ids=eligible_company_ids,
        eligible_security_codes=eligible_security_codes,
        company_decisions=tuple(company_decisions),
        security_decisions=tuple(sorted(security_decisions)),
    )


def _security_evidence_index(
    values: tuple[B3SecurityTradingEvidence, ...],
) -> dict[tuple[str, str], B3SecurityTradingEvidence]:
    indexed: dict[tuple[str, str], B3SecurityTradingEvidence] = {}
    for evidence in values:
        key = (evidence.company_id, evidence.code)
        if key in indexed:
            raise ValueError(
                "B3 current-security audit contains duplicate security evidence: "
                f"company_id={evidence.company_id} code={evidence.code}"
            )
        indexed[key] = evidence
    return indexed


def _classify_security(
    *,
    company_id: str,
    code: str,
    evidence: B3SecurityTradingEvidence | None,
    code_conflict: bool,
) -> CurrentBrazilianEquitySecurityDecision:
    if code_conflict:
        return _security_decision(
            company_id=company_id,
            code=code,
            status="EXCLUDED_SECURITY_CODE_IDENTITY_CONFLICT",
            evidence=evidence,
            security_kind=None,
            reason="The exact B3 security code is owned by multiple canonical company identities.",
        )
    if evidence is None or evidence.trade_days <= 0:
        return _security_decision(
            company_id=company_id,
            code=code,
            status="EXCLUDED_NO_CURRENT_SPOT_TRADE",
            evidence=evidence,
            security_kind=None,
            reason=(
                "The exact B3 security code has no spot-market trade in the current "
                "COTAHIST year."
            ),
        )

    taxonomy = classify_b3_security_specifications(evidence.specifications)
    if taxonomy.conflict:
        return _security_decision(
            company_id=company_id,
            code=code,
            status="EXCLUDED_SECURITY_TAXONOMY_CONFLICT",
            evidence=evidence,
            security_kind=None,
            reason=(
                "The exact B3 security code exhibits ESPECI values that resolve to "
                "multiple reviewed security kinds."
            ),
        )

    kind = taxonomy.coherent_kind or B3SecurityKind.OTHER_UNKNOWN
    if kind == B3SecurityKind.OTHER_UNKNOWN:
        return _security_decision(
            company_id=company_id,
            code=code,
            status="EXCLUDED_UNKNOWN_SECURITY_KIND",
            evidence=evidence,
            security_kind=kind.value,
            reason="The observed B3 ESPECI is not in the reviewed security taxonomy.",
        )
    if not taxonomy.core_equity_security:
        return _security_decision(
            company_id=company_id,
            code=code,
            status="EXCLUDED_NON_CORE_SECURITY_KIND",
            evidence=evidence,
            security_kind=kind.value,
            reason=(
                "The exact B3 security code trades currently but its reviewed ESPECI "
                f"kind is non-core for the Brazilian equity universe: {kind.value}."
            ),
        )
    return _security_decision(
        company_id=company_id,
        code=code,
        status="ELIGIBLE_CURRENT_CORE_EQUITY_SECURITY",
        evidence=evidence,
        security_kind=kind.value,
        reason=(
            "The exact B3 security code has current-year spot-market evidence and a "
            f"coherent reviewed core-equity ESPECI kind: {kind.value}."
        ),
    )


def _security_decision(
    *,
    company_id: str,
    code: str,
    status: CurrentBrazilianEquitySecurityStatus,
    evidence: B3SecurityTradingEvidence | None,
    security_kind: str | None,
    reason: str,
) -> CurrentBrazilianEquitySecurityDecision:
    return CurrentBrazilianEquitySecurityDecision(
        company_id=company_id,
        code=code,
        status=status,
        eligible=status == "ELIGIBLE_CURRENT_CORE_EQUITY_SECURITY",
        security_kind=security_kind,
        specifications=evidence.specifications if evidence else (),
        trade_days=evidence.trade_days if evidence else 0,
        first_trade_date=evidence.first_trade_date if evidence else None,
        last_trade_date=evidence.last_trade_date if evidence else None,
        detail_isin=evidence.detail_isin if evidence else None,
        observed_isins=evidence.observed_isins if evidence else (),
        reason=reason,
    )


def _company_decision(
    *,
    company: B3CompanyCurrentSecurityEvidence,
    issuer_status: str,
    status: CurrentBrazilianEquityCompanyStatus,
    eligible_security_codes: tuple[str, ...],
    excluded_security_codes: tuple[str, ...],
    reason: str,
) -> CurrentBrazilianEquityCompanyDecision:
    return CurrentBrazilianEquityCompanyDecision(
        company_id=company.company_id,
        issuer_code=company.issuer_code,
        trading_name=company.trading_name,
        issuer_status=issuer_status,
        status=status,
        eligible=status == "ELIGIBLE_CURRENT_BRAZILIAN_EQUITY",
        exact_security_codes=company.exact_security_codes,
        eligible_security_codes=eligible_security_codes,
        excluded_security_codes=excluded_security_codes,
        reason=reason,
    )
