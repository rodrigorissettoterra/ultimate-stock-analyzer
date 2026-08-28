from __future__ import annotations

from collections import defaultdict

from ultimate_stock_analyzer.macro.models import FactorState, MacroFactor, MacroObservation


def build_factor_states(
    observations: list[MacroObservation],
    *,
    min_history: int = 24,
    change_lag: int = 12,
    level_weight: float = 0.70,
) -> dict[MacroFactor, FactorState]:
    if min_history < 2:
        raise ValueError("min_history must be at least 2")
    if change_lag <= 0:
        raise ValueError("change_lag must be positive")
    if not 0.0 <= level_weight <= 1.0:
        raise ValueError("level_weight must be between 0 and 1")

    grouped: dict[MacroFactor, list[MacroObservation]] = defaultdict(list)
    for observation in observations:
        grouped[observation.factor].append(observation)

    states: dict[MacroFactor, FactorState] = {}
    for factor, raw_history in grouped.items():
        history = sorted(raw_history, key=lambda item: item.reference_date)
        values = [item.value for item in history]
        latest = history[-1]
        level_percentile = percentile_rank(values, latest.value)
        change_percentile: float | None = None
        if len(values) > change_lag:
            changes = [
                values[index] - values[index - change_lag]
                for index in range(change_lag, len(values))
            ]
            change_percentile = percentile_rank(changes, changes[-1])

        level_signal = 2.0 * level_percentile - 1.0
        if change_percentile is None:
            state_signal = level_signal
        else:
            trend_signal = 2.0 * change_percentile - 1.0
            state_signal = level_weight * level_signal + (1.0 - level_weight) * trend_signal
        history_confidence = min(1.0, len(values) / min_history)
        change_confidence = 1.0 if change_percentile is not None else 0.80
        states[factor] = FactorState(
            factor=factor,
            latest_value=latest.value,
            reference_date=latest.reference_date,
            level_percentile=level_percentile,
            change_percentile=change_percentile,
            state_signal=max(-1.0, min(1.0, state_signal)),
            confidence=history_confidence * change_confidence,
            observations=len(values),
        )
    return states


def percentile_rank(values: list[float], target: float) -> float:
    if not values:
        raise ValueError("values are required")
    less = sum(value < target for value in values)
    equal = sum(value == target for value in values)
    if len(values) == 1:
        return 0.5
    average_rank_zero_based = less + (equal - 1) / 2.0
    return average_rank_zero_based / (len(values) - 1)
