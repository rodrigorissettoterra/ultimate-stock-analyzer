from datetime import date

import pytest

from ultimate_stock_analyzer.macro.context import build_factor_states, percentile_rank
from ultimate_stock_analyzer.macro.models import MacroFactor, MacroObservation


def test_percentile_rank_uses_average_rank_for_ties() -> None:
    assert percentile_rank([1.0, 2.0, 2.0, 3.0], 2.0) == 0.5


def test_high_level_with_neutral_lagged_trend_uses_configured_mix() -> None:
    observations = [
        MacroObservation(
            factor=MacroFactor.SELIC,
            value=float(index),
            reference_date=date(2024, 1, 1).replace(
                month=(index % 12) + 1,
                year=2024 + index // 12,
            ),
            unit="percent_per_year",
            source="SYNTHETIC",
            source_series="test",
        )
        for index in range(1, 25)
    ]
    states = build_factor_states(observations, min_history=24, change_lag=12)
    state = states[MacroFactor.SELIC]
    assert state.level_percentile == 1.0
    assert state.change_percentile == 0.5
    assert state.state_signal == pytest.approx(0.70)
    assert state.confidence == 1.0
