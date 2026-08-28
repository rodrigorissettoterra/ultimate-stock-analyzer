from datetime import date

from ultimate_stock_analyzer.macro.context import build_factor_states, percentile_rank
from ultimate_stock_analyzer.macro.models import MacroFactor, MacroObservation


def test_percentile_rank_uses_average_rank_for_ties() -> None:
    assert percentile_rank([1.0, 2.0, 2.0, 3.0], 2.0) == 0.5


def test_high_current_value_produces_positive_factor_state_signal() -> None:
    observations = [
        MacroObservation(
            factor=MacroFactor.SELIC,
            value=float(index),
            reference_date=date(2024, 1, 1).replace(month=(index % 12) + 1, year=2024 + index // 12),
            unit="percent_per_year",
            source="SYNTHETIC",
            source_series="test",
        )
        for index in range(1, 25)
    ]
    states = build_factor_states(observations, min_history=24, change_lag=12)
    assert states[MacroFactor.SELIC].state_signal > 0.8
    assert states[MacroFactor.SELIC].confidence == 1.0
