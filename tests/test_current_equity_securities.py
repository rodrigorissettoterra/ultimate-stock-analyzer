from datetime import date

from ultimate_stock_analyzer.universe.b3_current_security_audit import (
    B3CompanyCurrentSecurityEvidence,
    B3CurrentSecurityAuditReport,
    B3SecurityTradingEvidence,
)
from ultimate_stock_analyzer.universe.current_equity_securities import (
    classify_current_brazilian_equity_securities,
)
from ultimate_stock_analyzer.universe.eligibility import (
    classify_brazilian_equity_issuers,
)


def _company(
    company_id: str,
    codes: tuple[str, ...],
    *,
    status: str = "B3_SHARE_DATE_WITH_CURRENT_SPOT_TRADE",
    conflicting_codes: tuple[str, ...] = (),
) -> B3CompanyCurrentSecurityEvidence:
    primary = codes[0] if codes else None
    return B3CompanyCurrentSecurityEvidence(
        company_id=company_id,
        cvm_code=int(company_id.split(":", 1)[1]),
        issuer_code=f"I{company_id.split(':', 1)[1]}",
        trading_name=f"Company {company_id}",
        cnpj=None,
        sector="Test",
        subsector="Test",
        segment="Test",
        status=status,
        reason="test evidence",
        share_quotation_start=date(2020, 1, 1),
        primary_code=primary,
        exact_security_codes=codes,
        traded_exact_codes=(
            codes if status == "B3_SHARE_DATE_WITH_CURRENT_SPOT_TRADE" else ()
        ),
        conflicting_security_codes=conflicting_codes,
    )


def _security(
    company_id: str,
    code: str,
    specifications: tuple[str, ...],
    *,
    trade_days: int = 10,
) -> B3SecurityTradingEvidence:
    return B3SecurityTradingEvidence(
        company_id=company_id,
        code=code,
        detail_isin=None,
        trade_days=trade_days,
        first_trade_date=date(2026, 1, 2) if trade_days else None,
        last_trade_date=date(2026, 8, 31) if trade_days else None,
        specifications=specifications,
        observed_isins=(),
    )


def _audit(
    companies: tuple[B3CompanyCurrentSecurityEvidence, ...],
    securities: tuple[B3SecurityTradingEvidence, ...] = (),
    *,
    code_conflicts: dict[str, tuple[str, ...]] | None = None,
) -> B3CurrentSecurityAuditReport:
    return B3CurrentSecurityAuditReport(
        candidate_company_ids=len(companies),
        company_status_counts={},
        detail_identity_conflicts=(),
        security_code_identity_conflicts=code_conflicts or {},
        share_quotation_date_present=0,
        share_quotation_date_missing=0,
        companies_with_current_spot_trade=0,
        cotahist_latest_trade_date=date(2026, 8, 31),
        specification_counts={},
        share_dated_specification_counts={},
        company_evidence=companies,
        security_evidence=securities,
    )


def _issuer_report(
    candidates: tuple[str, ...],
    *,
    brazilian: tuple[str, ...],
    foreign: tuple[str, ...] = (),
):
    return classify_brazilian_equity_issuers(
        candidates,
        brazilian_public_company_ids=brazilian,
        foreign_issuer_company_ids=foreign,
    )


def test_current_security_contract_accepts_domestic_common_share_with_spot_trade() -> None:
    company = _company("cvm:1", ("ONE3",))
    report = classify_current_brazilian_equity_securities(
        issuer_eligibility=_issuer_report(("cvm:1",), brazilian=("cvm:1",)),
        security_audit=_audit(
            (company,),
            (_security("cvm:1", "ONE3", ("ON NM",)),),
        ),
    )

    assert report.eligible_company_ids == ("cvm:1",)
    assert report.eligible_security_codes == ("ONE3",)
    assert report.security_decisions[0].security_kind == "COMMON_SHARE"


def test_current_security_contract_excludes_foreign_unit_before_security_promotion() -> None:
    company = _company(
        "cvm:2",
        ("PPLA11",),
        status="NO_B3_SHARE_QUOTATION_DATE",
    )
    report = classify_current_brazilian_equity_securities(
        issuer_eligibility=_issuer_report(
            ("cvm:2",),
            brazilian=(),
            foreign=("cvm:2",),
        ),
        security_audit=_audit(
            (company,),
            (_security("cvm:2", "PPLA11", ("UNT",)),),
        ),
    )

    assert report.eligible_company_count == 0
    assert report.company_decisions[0].status == "EXCLUDED_ISSUER_NOT_ELIGIBLE"
    assert report.security_decisions == ()


def test_current_security_contract_excludes_non_core_receipt_even_if_it_trades() -> None:
    company = _company("cvm:3", ("THR4",))
    report = classify_current_brazilian_equity_securities(
        issuer_eligibility=_issuer_report(("cvm:3",), brazilian=("cvm:3",)),
        security_audit=_audit(
            (company,),
            (_security("cvm:3", "THR4", ("PN REC",)),),
        ),
    )

    assert report.eligible_company_count == 0
    assert report.security_decisions[0].status == "EXCLUDED_NON_CORE_SECURITY_KIND"
    assert report.security_decisions[0].security_kind == "SUBSCRIPTION_RECEIPT"


def test_current_security_contract_excludes_exact_code_without_current_spot_trade() -> None:
    company = _company(
        "cvm:4",
        ("FOUR3",),
        status="B3_SHARE_DATE_WITHOUT_CURRENT_SPOT_TRADE",
    )
    report = classify_current_brazilian_equity_securities(
        issuer_eligibility=_issuer_report(("cvm:4",), brazilian=("cvm:4",)),
        security_audit=_audit(
            (company,),
            (_security("cvm:4", "FOUR3", ("ON",), trade_days=0),),
        ),
    )

    assert report.security_decisions[0].status == "EXCLUDED_NO_CURRENT_SPOT_TRADE"
    assert report.company_decisions[0].status == "EXCLUDED_NO_CURRENT_CORE_EQUITY_SECURITY"


def test_current_security_contract_fails_closed_on_detail_identity_problem() -> None:
    company = _company("cvm:5", ("FIVE3",), status="DETAIL_IDENTITY_CONFLICT")
    report = classify_current_brazilian_equity_securities(
        issuer_eligibility=_issuer_report(("cvm:5",), brazilian=("cvm:5",)),
        security_audit=_audit(
            (company,),
            (_security("cvm:5", "FIVE3", ("ON",)),),
        ),
    )

    assert report.company_decisions[0].status == "EXCLUDED_DETAIL_IDENTITY_CONFLICT"
    assert report.security_decisions == ()


def test_current_security_contract_keeps_non_core_code_beside_eligible_share() -> None:
    company = _company("cvm:6", ("SIX3", "SIX11"))
    report = classify_current_brazilian_equity_securities(
        issuer_eligibility=_issuer_report(("cvm:6",), brazilian=("cvm:6",)),
        security_audit=_audit(
            (company,),
            (
                _security("cvm:6", "SIX3", ("ON NM",)),
                _security("cvm:6", "SIX11", ("BNS ORD",)),
            ),
        ),
    )

    assert report.company_decisions[0].status == "ELIGIBLE_CURRENT_BRAZILIAN_EQUITY"
    assert report.company_decisions[0].eligible_security_codes == ("SIX3",)
    statuses = {item.code: item.status for item in report.security_decisions}
    assert statuses == {
        "SIX11": "EXCLUDED_NON_CORE_SECURITY_KIND",
        "SIX3": "ELIGIBLE_CURRENT_CORE_EQUITY_SECURITY",
    }


def test_current_security_contract_fails_company_closed_on_code_identity_conflict() -> None:
    company = _company(
        "cvm:7",
        ("SEVN3",),
        status="SECURITY_CODE_IDENTITY_CONFLICT",
        conflicting_codes=("SEVN3",),
    )
    report = classify_current_brazilian_equity_securities(
        issuer_eligibility=_issuer_report(("cvm:7",), brazilian=("cvm:7",)),
        security_audit=_audit(
            (company,),
            (_security("cvm:7", "SEVN3", ("ON",)),),
            code_conflicts={"SEVN3": ("cvm:7", "cvm:8")},
        ),
    )

    assert report.company_decisions[0].status == "EXCLUDED_SECURITY_CODE_IDENTITY_CONFLICT"
    assert report.security_decisions == ()


def test_current_security_contract_fails_unknown_and_taxonomy_conflict_closed() -> None:
    companies = (
        _company("cvm:8", ("EIGT3",)),
        _company("cvm:9", ("NINE4",)),
    )
    report = classify_current_brazilian_equity_securities(
        issuer_eligibility=_issuer_report(
            ("cvm:8", "cvm:9"),
            brazilian=("cvm:8", "cvm:9"),
        ),
        security_audit=_audit(
            companies,
            (
                _security("cvm:8", "EIGT3", ("XYZ",)),
                _security("cvm:9", "NINE4", ("PN", "PN REC")),
            ),
        ),
    )

    statuses = {item.code: item.status for item in report.security_decisions}
    assert statuses == {
        "EIGT3": "EXCLUDED_UNKNOWN_SECURITY_KIND",
        "NINE4": "EXCLUDED_SECURITY_TAXONOMY_CONFLICT",
    }
    assert report.eligible_company_count == 0
