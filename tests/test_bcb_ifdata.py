from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest

from ultimate_stock_analyzer.collectors.bcb_ifdata import (
    IFDataPrudentialIdentity,
    bank_contract_values,
    build_annual_bank_profile,
    cnpj_root,
    resolve_prudential_identity,
)
from ultimate_stock_analyzer.domain.master import IssuerRecord


def _payload(rows: list[dict[str, object]]) -> bytes:
    return json.dumps({"value": rows}, ensure_ascii=False).encode()


def _cadastro(ano_mes: int, cod_inst: str = "C0080099") -> bytes:
    return _payload(
        [
            {
                "CodInst": "60701190",
                "Data": str(ano_mes),
                "NomeInstituicao": "ITAÚ UNIBANCO S.A.",
                "CodConglomeradoPrudencial": cod_inst,
                "CnpjInstituicaoLider": "60872504",
                "Situacao": "A",
            },
            {
                "CodInst": cod_inst,
                "Data": str(ano_mes),
                "NomeInstituicao": "ITAU - PRUDENCIAL",
                "CodConglomeradoPrudencial": cod_inst,
                "CnpjInstituicaoLider": "60872504",
                "Situacao": "A",
            },
        ]
    )


def _report(cod_inst: str, values: dict[str, float]) -> bytes:
    return _payload(
        [
            {
                "CodInst": cod_inst,
                "Conta": account,
                "Saldo": value,
            }
            for account, value in values.items()
        ]
    )


def test_resolve_prudential_identity_uses_leader_cnpj_and_conglomerate_row() -> None:
    identity = resolve_prudential_identity(
        _cadastro(202512),
        cnpj="60.872.504/0001-23",
        ano_mes=202512,
    )

    assert identity is not None
    assert identity.cod_inst == "C0080099"
    assert identity.name == "ITAU - PRUDENCIAL"
    assert identity.leader_cnpj_root == "60872504"
    assert cnpj_root("60.872.504/0001-23") == "60872504"


def test_resolve_prudential_identity_fails_closed_on_ambiguity() -> None:
    rows = json.loads(_cadastro(202512))["value"]
    duplicate = dict(rows[-1])
    duplicate["NomeInstituicao"] = "DUPLICATE PRUDENTIAL"
    content = _payload([*rows, duplicate])

    with pytest.raises(ValueError, match="ambiguous IFData prudential identity"):
        resolve_prudential_identity(
            content,
            cnpj="60.872.504/0001-23",
            ano_mes=202512,
        )


def test_build_annual_profile_uses_two_semesters_and_verified_bank_metrics() -> None:
    issuer = IssuerRecord(
        company_id="cvm:19348",
        cvm_code=19348,
        cnpj="60.872.504/0001-23",
        legal_name="ITAÚ UNIBANCO HOLDING S.A.",
        collected_at=datetime(2026, 8, 29, tzinfo=UTC),
    )
    current = IFDataPrudentialIdentity(
        ano_mes=202512,
        cod_inst="C0080099",
        name="ITAU - PRUDENCIAL",
        leader_cnpj_root="60872504",
        prudential_code="C0080099",
        status="A",
    )
    prior = IFDataPrudentialIdentity(
        ano_mes=202412,
        cod_inst="C0080099",
        name="ITAU - PRUDENCIAL",
        leader_cnpj_root="60872504",
        prudential_code="C0080099",
        status="A",
    )
    first_half = IFDataPrudentialIdentity(
        ano_mes=202506,
        cod_inst="C0080099",
        name="ITAU - PRUDENCIAL",
        leader_cnpj_root="60872504",
        prudential_code="C0080099",
        status="A",
    )

    profile = build_annual_bank_profile(
        issuer=issuer,
        fiscal_year=2025,
        current_identity=current,
        prior_identity=prior,
        first_half_identity=first_half,
        prior_summary=_report(
            "C0080099",
            {
                "140220": 2_000.0,
                "140246": 200.0,
                "141873": 900.0,
            },
        ),
        first_half_income=_report(
            "C0080099",
            {
                "141870": 20.0,
                "141840": -9.0,
            },
        ),
        current_summary=_report(
            "C0080099",
            {
                "140220": 2_400.0,
                "140246": 240.0,
                "141873": 1_100.0,
            },
        ),
        second_half_income=_report(
            "C0080099",
            {
                "141870": 24.0,
                "141840": -11.0,
            },
        ),
        current_capital=_report(
            "C0080099",
            {
                "79664": 0.16,
                "79660": 0.14,
                "79659": 0.12,
                "79661": 0.07,
            },
        ),
        collected_at=datetime(2026, 8, 29, tzinfo=UTC),
    )

    assert profile.annual_net_income == pytest.approx(44.0)
    assert profile.annual_credit_loss_result == pytest.approx(-20.0)
    assert profile.roe == pytest.approx(44.0 / 220.0)
    assert profile.roa == pytest.approx(44.0 / 2_200.0)
    assert profile.cost_of_credit == pytest.approx(20.0 / 1_000.0)
    assert profile.equity_to_assets == pytest.approx(0.1)
    assert profile.basel_ratio == pytest.approx(0.16)
    assert profile.tier1_ratio == pytest.approx(0.14)
    assert profile.core_equity_tier1_ratio == pytest.approx(0.12)
    assert profile.leverage_ratio == pytest.approx(0.07)
    assert profile.available_from_estimate == datetime(2026, 4, 1, tzinfo=UTC)
    assert profile.point_in_time_eligible is False

    values = bank_contract_values(profile)
    assert values["annual_net_income"] == pytest.approx(44.0)
    assert "roe" not in values
