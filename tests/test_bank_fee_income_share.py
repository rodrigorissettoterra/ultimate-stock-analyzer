from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from ultimate_stock_analyzer.collectors.bcb_ifdata import (
    IFDataPrudentialIdentity,
    build_annual_bank_profile,
)
from ultimate_stock_analyzer.domain.master import IssuerRecord
from ultimate_stock_analyzer.scoring.structural import (
    StructuralScoringConfig,
    StructuralScoringEngine,
)


def _payload(rows: list[dict[str, object]]) -> bytes:
    return json.dumps({"value": rows}, ensure_ascii=False).encode()


def _report(cod_inst: str, values: dict[str, float]) -> bytes:
    return _payload(
        [
            {"CodInst": cod_inst, "Conta": account, "Saldo": value}
            for account, value in values.items()
        ]
    )


def _identity(ano_mes: int) -> IFDataPrudentialIdentity:
    return IFDataPrudentialIdentity(
        ano_mes=ano_mes,
        cod_inst="C0080099",
        name="ITAU - PRUDENCIAL",
        leader_cnpj_root="60872504",
        prudential_code="C0080099",
        status="A",
    )


def _issuer() -> IssuerRecord:
    return IssuerRecord(
        company_id="cvm:19348",
        cvm_code=19348,
        cnpj="60.872.504/0001-23",
        legal_name="ITAÚ UNIBANCO HOLDING S.A.",
        collected_at=datetime(2026, 8, 30, tzinfo=UTC),
    )


def _income_half(*, second: bool, omit_payment_result: bool = False) -> bytes:
    values = {
        "141870": 24.0 if second else 20.0,
        "141840": -11.0 if second else -9.0,
        "141859": -40.0 if second else -30.0,
        "141867": 100.0 if second else 80.0,
        "141842": -20.0 if second else -10.0,
        "141860": -3.0 if second else -2.0,
        "141856": 12.0 if second else 10.0,
        "141857": 18.0 if second else 20.0,
        "141855": 10.0 if second else 5.0,
        "141825": 110.0 if second else 100.0,
        "141830": 60.0 if second else 50.0,
        "141835": 210.0 if second else 200.0,
        "141836": 5.0,
        "141837": 20.0 if second else 15.0,
    }
    if omit_payment_result:
        values.pop("141855")
    return _report("C0080099", values)


def _build_profile(
    *,
    first_half_ano_mes: int = 202506,
    year_end_ano_mes: int = 202512,
    omit_payment_result_second_half: bool = False,
):
    return build_annual_bank_profile(
        issuer=_issuer(),
        fiscal_year=2025,
        current_identity=_identity(year_end_ano_mes),
        prior_identity=_identity(202412),
        first_half_identity=_identity(first_half_ano_mes),
        prior_summary=_report(
            "C0080099",
            {"78182": 2_000.0, "78186": 200.0, "78183": 900.0},
        ),
        first_half_income=_income_half(second=False),
        current_summary=_report(
            "C0080099",
            {"140220": 2_400.0, "140246": 240.0, "141873": 1_100.0},
        ),
        second_half_income=_income_half(
            second=True,
            omit_payment_result=omit_payment_result_second_half,
        ),
        current_capital=_report(
            "C0080099",
            {"79664": 0.16, "79660": 0.14, "79659": 0.12, "79661": 0.07},
        ),
        collected_at=datetime(2026, 8, 30, tzinfo=UTC),
    )


def test_post_2025_fee_income_share_uses_bcb_service_revenue_approximation() -> None:
    profile = _build_profile()

    assert profile.annual_service_income == pytest.approx(75.0)
    assert profile.annual_financial_intermediation_income == pytest.approx(775.0)
    assert profile.fee_income_share == pytest.approx(75.0 / 850.0)


def test_fee_income_share_is_unknown_when_any_required_component_is_missing() -> None:
    profile = _build_profile(omit_payment_result_second_half=True)

    assert profile.annual_service_income is None
    assert profile.fee_income_share is None


def test_fee_income_share_remains_unknown_before_verified_2025_layout() -> None:
    profile = _build_profile(first_half_ano_mes=202406, year_end_ano_mes=202412)

    assert profile.annual_service_income is None
    assert profile.annual_financial_intermediation_income is None
    assert profile.fee_income_share is None


def test_efficiency_and_fee_income_raise_verified_bank_coverage_to_60pct() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    engine = StructuralScoringEngine(
        StructuralScoringConfig.from_yaml(
            repo_root / "config/scoring/sectors/banks_v0.6.yml"
        )
    )
    result = engine.score_universe(
        [
            {
                "ticker": "ITUB4",
                "sector": "Financeiro",
                "peer_group": "banks",
                "roe": 0.20,
                "roa": 0.02,
                "cost_of_credit": 0.02,
                "basel_ratio": 0.16,
                "tier1_ratio": 0.14,
                "equity_to_assets": 0.10,
                "efficiency_ratio": 0.45,
                "fee_income_share": 0.12,
            }
        ]
    )[0]

    assert result.data_coverage == pytest.approx(0.60)
    assert result.rankable is False
    assert "LOW_STRUCTURAL_DATA_COVERAGE" in result.flags
