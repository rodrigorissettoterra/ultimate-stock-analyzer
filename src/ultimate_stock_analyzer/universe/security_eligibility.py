from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from typing import Literal

from ultimate_stock_analyzer.domain.master import SecurityRecord
from ultimate_stock_analyzer.universe.eligibility import (
    BrazilianEquityEligibilityReport,
)

CurrentSecurityEligibilityStatus = Literal[
    "ELIGIBLE_BRAZILIAN_LISTED_EQUITY_SECURITY",
    "EXCLUDED_ISSUER_NOT_ELIGIBLE",
    "EXCLUDED_INACTIVE_SECURITY",
    "EXCLUDED_NON_B3_ADMINISTRATOR",
    "EXCLUDED_NON_EXCHANGE_MARKET",
    "EXCLUDED_UNSUPPORTED_SECURITY_TYPE",
]
CurrentCompanySecurityEligibilityStatus = Literal[
    "ELIGIBLE_BRAZILIAN_LISTED_EQUITY_ISSUER",
    "EXCLUDED_ISSUER_NOT_ELIGIBLE",
    "EXCLUDED_NO_FCA_SECURITY_ROWS",
    "EXCLUDED_NO_ELIGIBLE_B3_EQUITY_SECURITY",
]

_ALLOWED_SECURITY_TYPES = frozenset(
    {"ações ordinárias", "ações preferenciais", "units"}
)


@dataclass(frozen=True, slots=True, order=True)
class CurrentSecurityEligibilityDecision:
    company_id: str
    ticker: str
    status: CurrentSecurityEligibilityStatus
    eligible: bool
    security_type: str | None
    market: str | None
    administrator: str | None
    active_as_of: bool
    reason: str


@dataclass(frozen=True, slots=True, order=True)
class CurrentCompanySecurityEligibilityDecision:
    company_id: str
    status: CurrentCompanySecurityEligibilityStatus
    eligible: bool
    eligible_tickers: tuple[str, ...]
    reason: str


@dataclass(frozen=True, slots=True)
class CurrentSecurityEligibilityReport:
    candidate_company_ids: int
    latest_security_rows: int
    eligible_company_ids: tuple[str, ...]
    eligible_tickers: tuple[str, ...]
    company_status_counts: dict[str, int]
    security_status_counts: dict[str, int]
    company_decisions: tuple[CurrentCompanySecurityEligibilityDecision, ...]
    security_decisions: tuple[CurrentSecurityEligibilityDecision, ...]
    scope: str = "CURRENT_STATE_ONLY"
    point_in_time_eligible: bool = False

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def classify_current_brazilian_equity_securities(
    candidate_company_ids: Iterable[str],
    securities: Iterable[SecurityRecord],
    *,
    issuer_eligibility_report: BrazilianEquityEligibilityReport,
    as_of: date,
) -> tuple[list[SecurityRecord], CurrentSecurityEligibilityReport]:
    candidates = tuple(sorted({_canonical_company_id(value) for value in candidate_company_ids}))
    issuer_decisions = {
        decision.company_id: decision
        for decision in issuer_eligibility_report.decisions
    }
    missing_issuer_decisions = sorted(set(candidates) - issuer_decisions.keys())
    if missing_issuer_decisions:
        raise ValueError(
            "Security eligibility candidates lack issuer eligibility decisions: "
            + ", ".join(missing_issuer_decisions[:10])
        )

    candidate_set = set(candidates)
    grouped: defaultdict[tuple[str, str], list[SecurityRecord]] = defaultdict(list)
    for security in securities:
        company_id = _canonical_company_id(security.company_id)
        if company_id not in candidate_set:
            continue
        ticker = security.ticker.strip().upper()
        if ticker:
            grouped[(company_id, ticker)].append(security)

    latest_by_company: defaultdict[str, list[SecurityRecord]] = defaultdict(list)
    for (company_id, _), rows in grouped.items():
        latest_by_company[company_id].append(max(rows, key=_security_rank))
    for rows in latest_by_company.values():
        rows.sort(key=lambda security: security.ticker.strip().upper())

    eligible_records: list[SecurityRecord] = []
    security_decisions: list[CurrentSecurityEligibilityDecision] = []
    company_decisions: list[CurrentCompanySecurityEligibilityDecision] = []

    for company_id in candidates:
        issuer_decision = issuer_decisions[company_id]
        rows = latest_by_company.get(company_id, [])
        if not issuer_decision.eligible:
            for security in rows:
                security_decisions.append(
                    _security_decision(
                        security,
                        status="EXCLUDED_ISSUER_NOT_ELIGIBLE",
                        eligible=False,
                        as_of=as_of,
                        reason=(
                            "The canonical issuer is outside the validated Brazilian-public-company "
                            "issuer universe; its securities cannot enter the equity universe."
                        ),
                    )
                )
            company_decisions.append(
                CurrentCompanySecurityEligibilityDecision(
                    company_id=company_id,
                    status="EXCLUDED_ISSUER_NOT_ELIGIBLE",
                    eligible=False,
                    eligible_tickers=(),
                    reason=issuer_decision.reason,
                )
            )
            continue

        if not rows:
            company_decisions.append(
                CurrentCompanySecurityEligibilityDecision(
                    company_id=company_id,
                    status="EXCLUDED_NO_FCA_SECURITY_ROWS",
                    eligible=False,
                    eligible_tickers=(),
                    reason=(
                        "No normalized FCA security row exists for the canonical issuer in the "
                        "current FCA snapshot; security eligibility fails closed."
                    ),
                )
            )
            continue

        company_eligible_records: list[SecurityRecord] = []
        for security in rows:
            decision = _classify_security(security, as_of=as_of)
            security_decisions.append(decision)
            if decision.eligible:
                company_eligible_records.append(security)
                eligible_records.append(security)

        eligible_tickers = tuple(
            sorted(security.ticker.strip().upper() for security in company_eligible_records)
        )
        if eligible_tickers:
            company_decisions.append(
                CurrentCompanySecurityEligibilityDecision(
                    company_id=company_id,
                    status="ELIGIBLE_BRAZILIAN_LISTED_EQUITY_ISSUER",
                    eligible=True,
                    eligible_tickers=eligible_tickers,
                    reason=(
                        "The issuer is jurisdiction-eligible and has at least one active B3/Bolsa "
                        "FCA security with an explicitly supported Brazilian equity security type."
                    ),
                )
            )
        else:
            company_decisions.append(
                CurrentCompanySecurityEligibilityDecision(
                    company_id=company_id,
                    status="EXCLUDED_NO_ELIGIBLE_B3_EQUITY_SECURITY",
                    eligible=False,
                    eligible_tickers=(),
                    reason=(
                        "The issuer is jurisdiction-eligible but none of its latest FCA security "
                        "rows satisfy the active B3/Bolsa supported-equity contract."
                    ),
                )
            )

    eligible_records.sort(key=lambda security: (security.company_id, security.ticker))
    company_counts = Counter(decision.status for decision in company_decisions)
    security_counts = Counter(decision.status for decision in security_decisions)
    return eligible_records, CurrentSecurityEligibilityReport(
        candidate_company_ids=len(candidates),
        latest_security_rows=sum(len(rows) for rows in latest_by_company.values()),
        eligible_company_ids=tuple(
            decision.company_id for decision in company_decisions if decision.eligible
        ),
        eligible_tickers=tuple(
            sorted({security.ticker.strip().upper() for security in eligible_records})
        ),
        company_status_counts=dict(sorted(company_counts.items())),
        security_status_counts=dict(sorted(security_counts.items())),
        company_decisions=tuple(company_decisions),
        security_decisions=tuple(sorted(security_decisions)),
    )


def _classify_security(
    security: SecurityRecord,
    *,
    as_of: date,
) -> CurrentSecurityEligibilityDecision:
    if not _active_as_of(security, as_of=as_of):
        return _security_decision(
            security,
            status="EXCLUDED_INACTIVE_SECURITY",
            eligible=False,
            as_of=as_of,
            reason="The latest FCA security row is not active on the current analysis date.",
        )
    if _normalized_text(security.administrator) != "b3":
        return _security_decision(
            security,
            status="EXCLUDED_NON_B3_ADMINISTRATOR",
            eligible=False,
            as_of=as_of,
            reason="The current FCA security administrator is not B3.",
        )
    if _normalized_text(security.market) != "bolsa":
        return _security_decision(
            security,
            status="EXCLUDED_NON_EXCHANGE_MARKET",
            eligible=False,
            as_of=as_of,
            reason="The current FCA security market is not Bolsa.",
        )
    if _normalized_text(security.security_type) not in _ALLOWED_SECURITY_TYPES:
        return _security_decision(
            security,
            status="EXCLUDED_UNSUPPORTED_SECURITY_TYPE",
            eligible=False,
            as_of=as_of,
            reason=(
                "The current FCA security type is outside the explicitly supported equity set: "
                "Ações Ordinárias, Ações Preferenciais or Units."
            ),
        )
    return _security_decision(
        security,
        status="ELIGIBLE_BRAZILIAN_LISTED_EQUITY_SECURITY",
        eligible=True,
        as_of=as_of,
        reason=(
            "The security belongs to an eligible Brazilian public-company issuer and is an active "
            "B3/Bolsa FCA security of an explicitly supported equity type."
        ),
    )


def _security_decision(
    security: SecurityRecord,
    *,
    status: CurrentSecurityEligibilityStatus,
    eligible: bool,
    as_of: date,
    reason: str,
) -> CurrentSecurityEligibilityDecision:
    return CurrentSecurityEligibilityDecision(
        company_id=_canonical_company_id(security.company_id),
        ticker=security.ticker.strip().upper(),
        status=status,
        eligible=eligible,
        security_type=security.security_type,
        market=security.market,
        administrator=security.administrator,
        active_as_of=_active_as_of(security, as_of=as_of),
        reason=reason,
    )


def _active_as_of(security: SecurityRecord, *, as_of: date) -> bool:
    if security.trading_start is not None and security.trading_start > as_of:
        return False
    return security.trading_end is None or security.trading_end >= as_of


def _security_rank(security: SecurityRecord) -> tuple[date, int, datetime]:
    reference_date = security.reference_date or date.min
    available_from = security.available_from or datetime.min.replace(tzinfo=UTC)
    return reference_date, security.version, available_from


def _canonical_company_id(value: str) -> str:
    company_id = str(value).strip().lower()
    if not company_id.startswith("cvm:"):
        raise ValueError(f"company_id must use cvm:<CD_CVM>: {company_id}")
    code = company_id.split(":", 1)[1]
    if not code.isdigit():
        raise ValueError(f"company_id must use numeric CD_CVM: {company_id}")
    return f"cvm:{int(code)}"


def _normalized_text(value: str | None) -> str:
    return str(value or "").strip().casefold()
