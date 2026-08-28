from datetime import date
from pathlib import Path

from ultimate_stock_analyzer.macro.engine import (
    analyze_macro_context,
    analyze_macro_scenario,
    load_macro_profile,
)
from ultimate_stock_analyzer.macro.models import FactorState, MacroFactor

CONFIG = Path("config/macro/macro_profiles_v1.3.yml")


def _state(factor: MacroFactor, signal: float) -> FactorState:
    return FactorState(
        factor=factor,
        latest_value=1.0,
        reference_date=date(2026, 8, 1),
        level_percentile=(signal + 1.0) / 2.0,
        change_percentile=None,
        state_signal=signal,
        confidence=1.0,
        observations=60,
    )


def test_high_rate_environment_hurts_real_estate_more_than_banks() -> None:
    states = {
        MacroFactor.SELIC: _state(MacroFactor.SELIC, 1.0),
        MacroFactor.ACTIVITY: _state(MacroFactor.ACTIVITY, 0.0),
        MacroFactor.UNEMPLOYMENT: _state(MacroFactor.UNEMPLOYMENT, 0.0),
        MacroFactor.INFLATION: _state(MacroFactor.INFLATION, 0.0),
        MacroFactor.LONG_RATES: _state(MacroFactor.LONG_RATES, 1.0),
        MacroFactor.CREDIT_GROWTH: _state(MacroFactor.CREDIT_GROWTH, 0.0),
    }
    real_estate = analyze_macro_context(states, profile=load_macro_profile(CONFIG, "real_estate"))
    banks = analyze_macro_context(states, profile=load_macro_profile(CONFIG, "banks"))
    assert real_estate.rankable and banks.rankable
    assert real_estate.score < banks.score


def test_scenario_engine_preserves_directional_hypotheses() -> None:
    profile = load_macro_profile(CONFIG, "commodity_exporter")
    favorable = analyze_macro_scenario(
        {MacroFactor.COMMODITY_PRICE: 1.0, MacroFactor.USD_BRL: 1.0},
        profile=profile,
    )
    adverse = analyze_macro_scenario(
        {MacroFactor.COMMODITY_PRICE: -1.0, MacroFactor.USD_BRL: -1.0},
        profile=profile,
    )
    assert favorable > 50 > adverse
