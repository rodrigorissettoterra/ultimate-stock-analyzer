from __future__ import annotations

import json
from datetime import UTC, date, datetime

import pytest

from ultimate_stock_analyzer.domain.master import (
    BankPrudentialAnnualRecord,
    IssuerRecord,
)
from ultimate_stock_analyzer.scoring.ifdata_applicability_audit import (
    audit_ifdata_issuer_applicability,
)


def _issuer() -> IssuerRecord:
    return IssuerRecord(
        company_id="cvm:6041",
        cvm_code=6041,
        cnpj="01.548.981/0001-79",
        legal_name="INVESTIMENTOS BEMGE S.A.",
        collected_at=datetime(2026, 9, 1, tzinfo=UTC),
    )


def _cadastro(rows: list[dict[str, object]]) -> bytes:
    return json.dumps({"value": rows}, ensure_ascii=False).encode()


def _prudential_cadastro() -> bytes:
    return _cadastro(
        [
            {
                "CodInst": "C0006041",
                "NomeInstituicao": "TEST PRUDENTIAL",
                "CodConglomeradoPrudencial": "C0006041",
                "CnpjInstituicaoLider": "01548981",
                "Situacao": "A",
            }
        ]
    )


def test_ifdata_applicability_preserves_no_identity_as_valid_diagnostic() -> None:
    audit = audit_ifdata_issuer_applicability(
        issuer=_issuer(),
        cadastro_content=_cadastro([]),
        ano_mes=202512,
    )

    assert audit.status == "NO_PRUDENTIAL_IDENTITY"
    assert audit.cnpj_root == "01548981"
    assert audit.prudential_identity is None
    assert audit.bank_profile_available is False
    assert audit.bank_contract_critical_coverage is None
    assert audit.bank_profile_metrics == {}
    assert audit.point_in_time_eligible is False


def test_ifdata_applicability_reports_exact_prudential_identity_without_profile() -> None:
    audit = audit_ifdata_issuer_applicability(
        issuer=_issuer(),
        cadastro_content=_prudential_cadastro(),
        ano_mes=202512,
    )

    assert audit.status == "EXACT_PRUDENTIAL_IDENTITY_FOUND"
    assert audit.prudential_identity is not None
    assert audit.prudential_identity.cod_inst == "C0006041"
    assert audit.bank_profile_available is False
    assert audit.bank_contract_critical_coverage is None


def test_ifdata_applicability_evaluates_bank_contract_when_profile_exists() -> None:
    profile = BankPrudentialAnnualRecord(
        company_id="cvm:6041",
        cvm_code=6041,
        cnpj="01.548.981/0001-79",
        cnpj_root="01548981",
        fiscal_year=2025,
        reference_date=date(2025, 12, 31),
        ifdata_cod_inst="C0006041",
        ifdata_name="TEST PRUDENTIAL",
        total_assets=1000.0,
        prior_total_assets=900.0,
        equity=100.0,
        prior_equity=90.0,
        gross_credit_portfolio=500.0,
        prior_gross_credit_portfolio=450.0,
        annual_net_income=20.0,
        annual_credit_loss_result=-5.0,
        basel_ratio=0.15,
        tier1_ratio=0.13,
        collected_at=datetime(2026, 9, 1, tzinfo=UTC),
    )

    audit = audit_ifdata_issuer_applicability(
        issuer=_issuer(),
        cadastro_content=_prudential_cadastro(),
        ano_mes=202512,
        profile=profile,
    )

    assert audit.status == "EXACT_PRUDENTIAL_IDENTITY_FOUND"
    assert audit.bank_profile_available is True
    assert audit.bank_contract_critical_coverage == pytest.approx(1.0)
    assert audit.bank_contract_missing_critical == ()
    assert audit.bank_profile_metrics["total_assets"] == pytest.approx(1000.0)
    assert audit.bank_profile_metrics["basel_ratio"] == pytest.approx(0.15)


def test_ifdata_applicability_rejects_profile_without_exact_identity() -> None:
    profile = BankPrudentialAnnualRecord(
        company_id="cvm:6041",
        cvm_code=6041,
        cnpj_root="01548981",
        fiscal_year=2025,
        reference_date=date(2025, 12, 31),
        ifdata_cod_inst="C0006041",
        ifdata_name="TEST PRUDENTIAL",
        collected_at=datetime(2026, 9, 1, tzinfo=UTC),
    )

    with pytest.raises(ValueError, match="no exact IFData prudential identity"):
        audit_ifdata_issuer_applicability(
            issuer=_issuer(),
            cadastro_content=_cadastro([]),
            ano_mes=202512,
            profile=profile,
        )
