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


def _build_profile(*, omit_other_loss_second_half: bool = False):
    second_half = {
        "141870": 24.0,
        "141840": -11.0,
        "141859": -40.0,
        "141867": 100.0,
        "141842": -20.0,
        "141860": -3.0,
    }
    if omit_other_loss_second_half:
        second_half.pop("141860")

    return build_annual_bank_profile(
        issuer=_issuer(),
        fiscal_year=2025,
        current_identity=_identity(202512),
        prior_identity=_identity(202412),
        first_half_identity=_identity(202506),
        prior_summary=_report(
            "C0080099",
            {"78182": 2_000.0, "78186": 200.0, "78183": 900.0},
        ),
        first_half_income=_report(
            "C0080099",
            {
                "141870": 20.0,
                "141840": -9.0,
                "141859": -30.0,
                "141867": 80.0,
                "141842": -10.0,
                "141860": -2.0,
            },
        ),
        current_summary=_report(
            "C0080099",
            {"140220": 2_400.0, "140246": 240.0, "141873": 1_100.0},
        ),
        second_half_income=_report("C0080099", second_half),
        current_capital=_report(
            "C0080099",
            {"79664": 0.16, "79660": 0.14, "79659": 0.12, "79661": 0.07},
        ),
        collected_at=datetime(2026, 8, 30, tzinfo=UTC),
    )


def test_efficiency_ratio_uses_bcb_post_2025_operating_result_ex_provisions() -> None:
    profile = _build_profile()

    assert profile.annual_administrative_expense == pytest.approx(70.0)
    assert profile.annual_operating_result_ex_provisions == pytest.approx(215.0)
    assert profile.efficiency_ratio == pytest.approx(70.0 / 215.0)


def test_efficiency_ratio_stays_unknown_when_required_ifdata_component_is_missing() -> None:
    profile = _build_profile(omit_other_loss_second_half=True)

    assert profile.annual_administrative_expense == pytest.approx(70.0)
    assert profile.annual_operating_result_ex_provisions is None
    assert profile.efficiency_ratio is None


def test_efficiency_ratio_remains_unknown_for_pre_2025_income_contract() -> None:
    profile = build_annual_bank_profile(
        issuer=_issuer(),
        fiscal_year=2024,
        current_identity=_identity(202412),
        prior_identity=_identity(202312),
        first_half_identity=_identity(202406),
        prior_summary=_report(
            "C0080099",
            {"78182": 1_800.0, "78186": 180.0, "78183": 800.0},
        ),
        first_half_income=_report("C0080099", {}),
        current_summary=_report(
            "C0080099",
            {"78182": 2_000.0, "78186": 200.0, "78183": 900.0},
        ),
        second_half_income=_report("C0080099", {}),
        current_capital=_report("C0080099", {}),
        collected_at=datetime(2026, 8, 30, tzinfo=UTC),
    )

    assert profile.annual_administrative_expense is None
    assert profile.annual_operating_result_ex_provisions is None
    assert profile.efficiency_ratio is None


def test_efficiency_metric_increases_bank_coverage_but_does_not_cross_rankability_gate() -> None:
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
                "efficiency_ratio": 0.50,
            }
        ]
    )[0]

    assert result.data_coverage == pytest.approx(0.555)
    assert result.rankable is False
    assert "LOW_STRUCTURAL_DATA_COVERAGE" in result.flags
