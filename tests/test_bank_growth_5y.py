from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from ultimate_stock_analyzer.domain.master import BankPrudentialAnnualRecord
from ultimate_stock_analyzer.scoring.bank_growth import (
    bank_growth_features,
    derive_bank_growth_metrics,
)
from ultimate_stock_analyzer.scoring.structural import (
    StructuralScoringConfig,
    StructuralScoringEngine,
)


def _profile(
    year: int,
    *,
    net_income: float | None,
    loans: float | None,
    cod_inst: str = "C0080099",
) -> BankPrudentialAnnualRecord:
    return BankPrudentialAnnualRecord(
        company_id="cvm:19348",
        cvm_code=19348,
        cnpj="60.872.504/0001-23",
        cnpj_root="60872504",
        fiscal_year=year,
        reference_date=date(year, 12, 31),
        ifdata_cod_inst=cod_inst,
        ifdata_name="ITAU - PRUDENCIAL",
        gross_credit_portfolio=loans,
        annual_net_income=net_income,
        collected_at=datetime(2026, 8, 30, tzinfo=UTC),
    )


def _history() -> list[BankPrudentialAnnualRecord]:
    return [
        _profile(2020, net_income=20.0, loans=100.0),
        _profile(2021, net_income=22.0, loans=110.0),
        _profile(2022, net_income=24.0, loans=121.0),
        _profile(2023, net_income=27.0, loans=133.1),
        _profile(2024, net_income=30.0, loans=146.41),
        _profile(2025, net_income=40.0, loans=161.051),
    ]


def test_bank_growth_uses_exact_five_year_endpoint_distance() -> None:
    metrics = derive_bank_growth_metrics(
        _history(), company_id="cvm:19348", fiscal_year=2025
    )

    assert metrics.start_year == 2020
    assert metrics.end_year == 2025
    assert metrics.net_income_cagr_5y == pytest.approx(2.0 ** (1.0 / 5.0) - 1.0)
    assert metrics.loan_cagr_5y == pytest.approx(0.10)
    assert metrics.point_in_time_eligible is False


def test_bank_growth_requires_six_consecutive_annual_profiles() -> None:
    history = [profile for profile in _history() if profile.fiscal_year != 2022]

    metrics = derive_bank_growth_metrics(
        history, company_id="cvm:19348", fiscal_year=2025
    )

    assert metrics.net_income_cagr_5y is None
    assert metrics.loan_cagr_5y is None


def test_bank_growth_fails_closed_when_prudential_identity_changes() -> None:
    history = _history()
    history[2] = _profile(
        2022,
        net_income=24.0,
        loans=121.0,
        cod_inst="C9999999",
    )

    metrics = derive_bank_growth_metrics(
        history, company_id="cvm:19348", fiscal_year=2025
    )

    assert metrics.net_income_cagr_5y is None
    assert metrics.loan_cagr_5y is None


def test_net_income_cagr_is_unknown_for_non_positive_endpoint() -> None:
    history = _history()
    history[0] = _profile(2020, net_income=-1.0, loans=100.0)

    features = bank_growth_features(
        history, company_id="cvm:19348", fiscal_year=2025
    )

    assert features["net_income_cagr_5y"] is None
    assert features["loan_cagr_5y"] == pytest.approx(0.10)


def test_verified_growth_features_raise_bank_coverage_to_65pct() -> None:
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
                "loan_cagr_5y": 0.10,
                "net_income_cagr_5y": 0.15,
            }
        ]
    )[0]

    assert result.data_coverage == pytest.approx(0.65)
    assert "LOW_STRUCTURAL_DATA_COVERAGE" not in result.flags
