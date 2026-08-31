from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from datetime import date

from ultimate_stock_analyzer.collectors.b3_company_detail import B3ListedCompanyDetail
from ultimate_stock_analyzer.collectors.b3_cotahist_securities import (
    B3CotahistSecurityObservation,
)
from ultimate_stock_analyzer.domain.master import SectorClassificationRecord


@dataclass(frozen=True, slots=True)
class B3SecurityTradingEvidence:
    company_id: str
    code: str
    detail_isin: str | None
    trade_days: int
    first_trade_date: date | None
    last_trade_date: date | None
    specifications: tuple[str, ...]
    observed_isins: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class B3CompanyCurrentSecurityEvidence:
    company_id: str
    cvm_code: int
    issuer_code: str
    trading_name: str
    cnpj: str | None
    sector: str
    subsector: str
    segment: str
    status: str
    reason: str
    share_quotation_start: date | None
    primary_code: str | None
    exact_security_codes: tuple[str, ...]
    traded_exact_codes: tuple[str, ...]
    conflicting_security_codes: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class B3CurrentSecurityAuditReport:
    candidate_company_ids: int
    company_status_counts: dict[str, int]
    detail_identity_conflicts: tuple[str, ...]
    security_code_identity_conflicts: dict[str, tuple[str, ...]]
    share_quotation_date_present: int
    share_quotation_date_missing: int
    companies_with_current_spot_trade: int
    cotahist_latest_trade_date: date | None
    specification_counts: dict[str, int]
    share_dated_specification_counts: dict[str, int]
    company_evidence: tuple[B3CompanyCurrentSecurityEvidence, ...]
    security_evidence: tuple[B3SecurityTradingEvidence, ...]
    scope: str = "CURRENT_B3_GET_DETAIL_COTAHIST_DIAGNOSTIC"
    point_in_time_eligible: bool = False

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def audit_b3_current_security_state(
    classifications: list[SectorClassificationRecord],
    details_by_company: dict[str, B3ListedCompanyDetail],
    observations: list[B3CotahistSecurityObservation],
    *,
    detail_errors: dict[str, str] | None = None,
) -> B3CurrentSecurityAuditReport:
    errors = detail_errors or {}
    by_company = {record.company_id: record for record in classifications}
    if len(by_company) != len(classifications):
        raise ValueError("B3 classifications contain duplicate company_id values")

    conflicts: set[str] = set()
    valid: dict[str, B3ListedCompanyDetail] = {}
    for company_id, classification in sorted(by_company.items()):
        detail = details_by_company.get(company_id)
        if detail is None:
            continue
        if detail.company_id != company_id:
            conflicts.add(company_id)
            continue
        if detail.issuer_code and detail.issuer_code != classification.issuer_code:
            conflicts.add(company_id)
            continue
        if (
            detail.cnpj
            and classification.cnpj
            and _digits(detail.cnpj) != _digits(classification.cnpj)
        ):
            conflicts.add(company_id)
            continue
        valid[company_id] = detail

    owners: defaultdict[str, set[str]] = defaultdict(set)
    detail_isin: dict[tuple[str, str], str | None] = {}
    for company_id, detail in valid.items():
        isin_by_code = {item.code: item.isin for item in detail.security_codes}
        for code in detail.all_security_codes:
            normalized = _code(code)
            owners[normalized].add(company_id)
            detail_isin[(company_id, normalized)] = isin_by_code.get(normalized)
    code_conflicts = {
        code: tuple(sorted(company_ids))
        for code, company_ids in sorted(owners.items())
        if len(company_ids) > 1
    }

    observed: defaultdict[str, list[B3CotahistSecurityObservation]] = defaultdict(list)
    latest_trade_date: date | None = None
    for row in observations:
        observed[_code(row.ticker)].append(row)
        if latest_trade_date is None or row.trade_date > latest_trade_date:
            latest_trade_date = row.trade_date

    securities: list[B3SecurityTradingEvidence] = []
    company_securities: defaultdict[str, list[B3SecurityTradingEvidence]] = defaultdict(list)
    for code, company_ids in sorted(owners.items()):
        if len(company_ids) != 1:
            continue
        company_id = next(iter(company_ids))
        rows = sorted(observed.get(code, ()), key=lambda item: item.trade_date)
        evidence = B3SecurityTradingEvidence(
            company_id=company_id,
            code=code,
            detail_isin=detail_isin.get((company_id, code)),
            trade_days=len({row.trade_date for row in rows}),
            first_trade_date=rows[0].trade_date if rows else None,
            last_trade_date=rows[-1].trade_date if rows else None,
            specifications=tuple(sorted({row.specification for row in rows if row.specification})),
            observed_isins=tuple(sorted({row.isin for row in rows if row.isin})),
        )
        securities.append(evidence)
        company_securities[company_id].append(evidence)

    companies: list[B3CompanyCurrentSecurityEvidence] = []
    for company_id, classification in sorted(by_company.items()):
        detail = details_by_company.get(company_id)
        exact: tuple[str, ...] = ()
        traded: tuple[str, ...] = ()
        conflicting: tuple[str, ...] = ()
        share_start: date | None = None
        primary: str | None = None
        if company_id in errors:
            status, reason = "DETAIL_UNAVAILABLE", errors[company_id]
        elif detail is None:
            status, reason = "DETAIL_UNAVAILABLE", "B3 GetDetail returned no typed detail"
        elif company_id in conflicts:
            status = "DETAIL_IDENTITY_CONFLICT"
            reason = "B3 GetDetail identity conflicts with canonical B3 classification"
            exact = tuple(_code(code) for code in detail.all_security_codes)
            share_start, primary = detail.share_quotation_start, detail.primary_code
        else:
            exact = tuple(_code(code) for code in detail.all_security_codes)
            share_start, primary = detail.share_quotation_start, detail.primary_code
            conflicting = tuple(sorted(code for code in exact if code in code_conflicts))
            traded = tuple(sorted(
                item.code
                for item in company_securities.get(company_id, ())
                if item.trade_days > 0
            ))
            if conflicting:
                status = "SECURITY_CODE_IDENTITY_CONFLICT"
                reason = "exact B3 security code maps to multiple canonical companies"
            elif share_start is None:
                status = "NO_B3_SHARE_QUOTATION_DATE"
                reason = "B3 GetDetail has no dateQuotation / share quotation start"
            elif traded:
                status = "B3_SHARE_DATE_WITH_CURRENT_SPOT_TRADE"
                reason = "B3 share quotation date exists and an exact code traded in COTAHIST"
            else:
                status = "B3_SHARE_DATE_WITHOUT_CURRENT_SPOT_TRADE"
                reason = "B3 share quotation date exists but no exact code traded in current COTAHIST"
        companies.append(B3CompanyCurrentSecurityEvidence(
            company_id=company_id,
            cvm_code=classification.cvm_code,
            issuer_code=classification.issuer_code,
            trading_name=classification.trading_name,
            cnpj=classification.cnpj,
            sector=classification.sector,
            subsector=classification.subsector,
            segment=classification.segment,
            status=status,
            reason=reason,
            share_quotation_start=share_start,
            primary_code=primary,
            exact_security_codes=exact,
            traded_exact_codes=traded,
            conflicting_security_codes=conflicting,
        ))

    statuses = Counter(item.status for item in companies)
    specs: Counter[str] = Counter()
    share_specs: Counter[str] = Counter()
    share_companies = {
        company_id for company_id, detail in valid.items()
        if detail.share_quotation_start is not None
    }
    for item in securities:
        if item.trade_days <= 0:
            continue
        for specification in item.specifications:
            specs[specification] += 1
            if item.company_id in share_companies:
                share_specs[specification] += 1

    return B3CurrentSecurityAuditReport(
        candidate_company_ids=len(classifications),
        company_status_counts=dict(sorted(statuses.items())),
        detail_identity_conflicts=tuple(sorted(conflicts)),
        security_code_identity_conflicts=code_conflicts,
        share_quotation_date_present=sum(
            detail.share_quotation_start is not None for detail in valid.values()
        ),
        share_quotation_date_missing=sum(
            detail.share_quotation_start is None for detail in valid.values()
        ),
        companies_with_current_spot_trade=sum(bool(item.traded_exact_codes) for item in companies),
        cotahist_latest_trade_date=latest_trade_date,
        specification_counts=dict(sorted(specs.items())),
        share_dated_specification_counts=dict(sorted(share_specs.items())),
        company_evidence=tuple(companies),
        security_evidence=tuple(securities),
    )


def _digits(value: str) -> str:
    return "".join(character for character in value if character.isdigit())


def _code(value: str) -> str:
    code = value.strip().upper()
    if not code:
        raise ValueError("security code must not be blank")
    return code
