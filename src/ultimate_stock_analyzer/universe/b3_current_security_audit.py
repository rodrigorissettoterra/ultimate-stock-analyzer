from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from datetime import date

from ultimate_stock_analyzer.collectors.b3_company_detail import B3ListedCompanyDetail
from ultimate_stock_analyzer.collectors.b3_classification import SectorClassificationRecord
from ultimate_stock_analyzer.collectors.b3_cotahist_securities import (
    B3CotahistSecurityObservation,
)


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

    identity_conflicts: set[str] = set()
    valid_details: dict[str, B3ListedCompanyDetail] = {}
    for company_id, classification in sorted(by_company.items()):
        detail = details_by_company.get(company_id)
        if detail is None:
            continue
        if detail.company_id != company_id:
            identity_conflicts.add(company_id)
            continue
        if detail.issuer_code and detail.issuer_code != classification.issuer_code:
            identity_conflicts.add(company_id)
            continue
        if detail.cnpj and classification.cnpj:
            if _digits(detail.cnpj) != _digits(classification.cnpj):
                identity_conflicts.add(company_id)
                continue
        valid_details[company_id] = detail

    code_owners: defaultdict[str, set[str]] = defaultdict(set)
    detail_isin_by_company_code: dict[tuple[str, str], str | None] = {}
    for company_id, detail in valid_details.items():
        isin_by_code = {
            item.code: item.isin
            for item in detail.security_codes
        }
        for code in detail.all_security_codes:
            normalized = _code(code)
            code_owners[normalized].add(company_id)
            detail_isin_by_company_code[(company_id, normalized)] = isin_by_code.get(
                normalized
            )

    code_conflicts = {
        code: tuple(sorted(owners))
        for code, owners in sorted(code_owners.items())
        if len(owners) > 1
    }

    observations_by_code: defaultdict[str, list[B3CotahistSecurityObservation]] = (
        defaultdict(list)
    )
    latest_trade_date: date | None = None
    for observation in observations:
        code = _code(observation.ticker)
        observations_by_code[code].append(observation)
        if latest_trade_date is None or observation.trade_date > latest_trade_date:
            latest_trade_date = observation.trade_date

    security_evidence: list[B3SecurityTradingEvidence] = []
    evidence_by_company: defaultdict[str, list[B3SecurityTradingEvidence]] = defaultdict(list)
    for code, owners in sorted(code_owners.items()):
        if len(owners) != 1:
            continue
        company_id = next(iter(owners))
        rows = sorted(observations_by_code.get(code, ()), key=lambda item: item.trade_date)
        evidence = B3SecurityTradingEvidence(
            company_id=company_id,
            code=code,
            detail_isin=detail_isin_by_company_code.get((company_id, code)),
            trade_days=len({row.trade_date for row in rows}),
            first_trade_date=rows[0].trade_date if rows else None,
            last_trade_date=rows[-1].trade_date if rows else None,
            specifications=tuple(
                sorted({row.specification for row in rows if row.specification})
            ),
            observed_isins=tuple(sorted({row.isin for row in rows if row.isin})),
        )
        security_evidence.append(evidence)
        evidence_by_company[company_id].append(evidence)

    company_evidence: list[B3CompanyCurrentSecurityEvidence] = []
    for company_id, classification in sorted(by_company.items()):
        detail = details_by_company.get(company_id)
        exact_codes: tuple[str, ...] = ()
        traded_codes: tuple[str, ...] = ()
        conflicting_codes: tuple[str, ...] = ()
        share_start: date | None = None
        primary_code: str | None = None

        if company_id in errors:
            status = "DETAIL_UNAVAILABLE"
            reason = errors[company_id]
        elif detail is None:
            status = "DETAIL_UNAVAILABLE"
            reason = "B3 GetDetail returned no typed detail"
        elif company_id in identity_conflicts:
            status = "DETAIL_IDENTITY_CONFLICT"
            reason = "B3 GetDetail identity fields conflict with canonical B3 classification"
            exact_codes = tuple(_code(code) for code in detail.all_security_codes)
            share_start = detail.share_quotation_start
            primary_code = detail.primary_code
        else:
            assert company_id in valid_details
            exact_codes = tuple(_code(code) for code in detail.all_security_codes)
            conflicting_codes = tuple(
                sorted(code for code in exact_codes if code in code_conflicts)
            )
            share_start = detail.share_quotation_start
            primary_code = detail.primary_code
            traded_codes = tuple(
                sorted(
                    evidence.code
                    for evidence in evidence_by_company.get(company_id, ())
                    if evidence.trade_days > 0
                )
            )
            if conflicting_codes:
                status = "SECURITY_CODE_IDENTITY_CONFLICT"
                reason = "one or more exact B3 security codes map to multiple canonical companies"
            elif share_start is None:
                status = "NO_B3_SHARE_QUOTATION_DATE"
                reason = "B3 GetDetail has no dateQuotation / share quotation start"
            elif traded_codes:
                status = "B3_SHARE_DATE_WITH_CURRENT_SPOT_TRADE"
                reason = "B3 share quotation date exists and an exact returned code traded in COTAHIST"
            else:
                status = "B3_SHARE_DATE_WITHOUT_CURRENT_SPOT_TRADE"
                reason = "B3 share quotation date exists but no exact returned code traded in current COTAHIST"

        company_evidence.append(
            B3CompanyCurrentSecurityEvidence(
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
                primary_code=primary_code,
                exact_security_codes=exact_codes,
                traded_exact_codes=traded_codes,
                conflicting_security_codes=conflicting_codes,
            )
        )

    status_counts = Counter(item.status for item in company_evidence)
    specification_counts: Counter[str] = Counter()
    share_dated_specification_counts: Counter[str] = Counter()
    share_dated_companies = {
        company_id
        for company_id, detail in valid_details.items()
        if detail.share_quotation_start is not None
    }
    for evidence in security_evidence:
        if evidence.trade_days <= 0:
            continue
        for specification in evidence.specifications:
            specification_counts[specification] += 1
            if evidence.company_id in share_dated_companies:
                share_dated_specification_counts[specification] += 1

    return B3CurrentSecurityAuditReport(
        candidate_company_ids=len(classifications),
        company_status_counts=dict(sorted(status_counts.items())),
        detail_identity_conflicts=tuple(sorted(identity_conflicts)),
        security_code_identity_conflicts=code_conflicts,
        share_quotation_date_present=sum(
            1
            for detail in valid_details.values()
            if detail.share_quotation_start is not None
        ),
        share_quotation_date_missing=sum(
            1
            for detail in valid_details.values()
            if detail.share_quotation_start is None
        ),
        companies_with_current_spot_trade=sum(
            1 for item in company_evidence if item.traded_exact_codes
        ),
        cotahist_latest_trade_date=latest_trade_date,
        specification_counts=dict(sorted(specification_counts.items())),
        share_dated_specification_counts=dict(
            sorted(share_dated_specification_counts.items())
        ),
        company_evidence=tuple(company_evidence),
        security_evidence=tuple(security_evidence),
    )


def _digits(value: str) -> str:
    return "".join(character for character in value if character.isdigit())


def _code(value: str) -> str:
    code = value.strip().upper()
    if not code:
        raise ValueError("security code must not be blank")
    return code
