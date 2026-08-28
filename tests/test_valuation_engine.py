from pathlib import Path

import pytest

from ultimate_stock_analyzer.valuation.engine import (
    ValuationConfig,
    ValuationEngine,
    ValuationEstimate,
    ValuationStatus,
)

CONFIG = Path("config/valuation/valuation_v0.7.yml")


def _estimate(model: str, value: float, confidence: float = 0.90) -> ValuationEstimate:
    return ValuationEstimate(
        model_id=model,
        fair_value_per_share=value,
        confidence=confidence,
        low_value_per_share=value * 0.90,
        high_value_per_share=value * 1.10,
        provenance=("TEST",),
    )


def test_bank_policy_ignores_inappropriate_enterprise_multiple() -> None:
    engine = ValuationEngine(ValuationConfig.from_yaml(CONFIG))
    base = [
        _estimate("residual_income", 30.0),
        _estimate("pb_peer", 28.0),
        _estimate("pe_peer", 32.0),
    ]
    result = engine.evaluate(
        ticker="BANK3",
        current_price=24.0,
        model_family="bank_v1",
        estimates=base,
    )
    with_rogue = engine.evaluate(
        ticker="BANK3",
        current_price=24.0,
        model_family="bank_v1",
        estimates=[*base, _estimate("ev_ebitda_peer", 999.0)],
    )

    assert result.blended_fair_value == with_rogue.blended_fair_value
    assert result.data_coverage == pytest.approx(1.0)
    assert result.rankable
    assert {item.model_id for item in result.estimates} == {
        "residual_income",
        "pb_peer",
        "pe_peer",
    }


def test_market_price_changes_margin_not_intrinsic_fair_value() -> None:
    engine = ValuationEngine(ValuationConfig.from_yaml(CONFIG))
    estimates = [
        _estimate("dcf_fcff", 30.0),
        _estimate("pe_peer", 28.0),
        _estimate("ev_ebitda_peer", 32.0),
        _estimate("p_fcf_peer", 31.0),
    ]
    cheap = engine.evaluate(
        ticker="CORP3",
        current_price=20.0,
        model_family="general_corporate_v1",
        estimates=estimates,
    )
    expensive = engine.evaluate(
        ticker="CORP3",
        current_price=40.0,
        model_family="general_corporate_v1",
        estimates=estimates,
    )

    assert cheap.blended_fair_value == expensive.blended_fair_value
    assert cheap.confidence == pytest.approx(expensive.confidence)
    assert cheap.valuation_score > expensive.valuation_score
    assert cheap.margin_of_safety > expensive.margin_of_safety


def test_low_model_coverage_abstains_from_valuation_label() -> None:
    engine = ValuationEngine(ValuationConfig.from_yaml(CONFIG))
    result = engine.evaluate(
        ticker="CORP3",
        current_price=20.0,
        model_family="general_corporate_v1",
        estimates=[_estimate("pe_peer", 30.0)],
    )

    assert not result.rankable
    assert result.status == ValuationStatus.INSUFFICIENT_DATA
    assert "LOW_VALUATION_MODEL_COVERAGE" in result.flags


def test_large_model_disagreement_is_visible() -> None:
    engine = ValuationEngine(ValuationConfig.from_yaml(CONFIG))
    result = engine.evaluate(
        ticker="CORP3",
        current_price=30.0,
        model_family="general_corporate_v1",
        estimates=[
            _estimate("dcf_fcff", 15.0),
            _estimate("pe_peer", 30.0),
            _estimate("ev_ebitda_peer", 60.0),
            _estimate("p_fcf_peer", 90.0),
        ],
    )

    assert result.model_dispersion is not None
    assert result.model_dispersion > 0.35
    assert "HIGH_VALUATION_MODEL_DISPERSION" in result.flags
