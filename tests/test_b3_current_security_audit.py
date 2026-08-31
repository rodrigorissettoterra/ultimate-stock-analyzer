from datetime import UTC, date, datetime

from ultimate_stock_analyzer.collectors.b3_company_detail import (
    B3ListedCompanyDetail,
    B3ListedSecurityCode,
)
from ultimate_stock_analyzer.collectors.b3_cotahist_securities import (
    B3CotahistSecurityObservation,
)
from ultimate_stock_analyzer.domain.master import SectorClassificationRecord
from ultimate_stock_analyzer.universe.b3_current_security_audit import (
    audit_b3_current_security_state,
)

NOW = datetime(2026, 8, 31, tzinfo=UTC)


def _classification(company_id: str, cvm_code: int, issuer_code: str, cnpj: str) -> SectorClassificationRecord:
    return SectorClassificationRecord(
        company_id=company_id,
        cvm_code=cvm_code,
        cnpj=cnpj,
        issuer_code=issuer_code,
        trading_name=issuer_code,
        sector="Setor",
        subsector="Subsetor",
        segment="Segmento",
        collected_at=NOW,
    )


def _detail(company_id: str, cvm_code: int, issuer_code: str, cnpj: str, code: str, share_start: date | None) -> B3ListedCompanyDetail:
    return B3ListedCompanyDetail(
        company_id=company_id,
        cvm_code=cvm_code,
        cnpj=cnpj,
        issuer_code=issuer_code,
        primary_code=code,
        security_codes=(B3ListedSecurityCode(code=code, isin=f"ISIN{cvm_code}"),),
        share_quotation_start=share_start,
        collected_at=NOW,
    )


def test_current_security_audit_separates_share_trade_from_no_share_date() -> None:
    classifications = [
        _classification("cvm:1", 1, "ONE", "11111111000111"),
        _classification("cvm:2", 2, "TWO", "22222222000122"),
    ]
    details = {
        "cvm:1": _detail("cvm:1", 1, "ONE", "11111111000111", "ONE3", date(2020, 1, 2)),
        "cvm:2": _detail("cvm:2", 2, "TWO", "22222222000122", "TWO-CRI", None),
    }
    observations = [
        B3CotahistSecurityObservation(
            ticker="ONE3",
            trade_date=date(2026, 8, 31),
            market_code=10,
            specification="ON",
            isin="ISIN1",
        )
    ]

    report = audit_b3_current_security_state(classifications, details, observations)
    by_id = {row.company_id: row for row in report.company_evidence}
    assert by_id["cvm:1"].status == "B3_SHARE_DATE_WITH_CURRENT_SPOT_TRADE"
    assert by_id["cvm:2"].status == "NO_B3_SHARE_QUOTATION_DATE"
    assert report.share_dated_specification_counts == {"ON": 1}


def test_current_security_audit_fails_closed_on_detail_identity_conflict() -> None:
    classifications = [_classification("cvm:1", 1, "ONE", "11111111000111")]
    details = {
        "cvm:1": _detail("cvm:1", 1, "ONE", "99999999000199", "ONE3", date(2020, 1, 2))
    }

    report = audit_b3_current_security_state(classifications, details, [])
    assert report.company_evidence[0].status == "DETAIL_IDENTITY_CONFLICT"
    assert report.detail_identity_conflicts == ("cvm:1",)
