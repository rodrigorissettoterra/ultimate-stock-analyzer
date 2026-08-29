from datetime import date

import pytest

from ultimate_stock_analyzer.backtesting.walk_forward import (
    CalibrationObservation,
    CalibrationPolicy,
    WeightCandidate,
    generate_local_candidates,
    make_expanding_folds,
    run_walk_forward_calibration,
)


def _baseline() -> WeightCandidate:
    return WeightCandidate("baseline", {"quality": 0.60, "valuation": 0.40})


def test_local_candidates_preserve_weight_contracts() -> None:
    baseline = _baseline()
    policy = CalibrationPolicy(max_abs_weight_change=0.05, max_l1_drift=0.10)
    candidates = generate_local_candidates(baseline, step=0.02, policy=policy)
    assert len(candidates) > 1
    for candidate in candidates:
        assert sum(candidate.weights.values()) == pytest.approx(1.0)
        assert all(value >= 0 for value in candidate.weights.values())
        assert max(
            abs(candidate.weights[name] - baseline.weights[name]) for name in baseline.weights
        ) <= 0.05


def test_training_cannot_use_forward_outcome_that_arrives_in_test_window() -> None:
    observations = [
        CalibrationObservation(
            decision_date=date(2024, 1, 1),
            outcome_available_date=date(2024, 4, 1),
            ticker=f"T{index}",
            component_scores={"quality": float(index), "valuation": float(10 - index)},
            forward_excess_return=float(index),
        )
        for index in range(1, 5)
    ]
    observations.extend(
        CalibrationObservation(
            decision_date=date(2024, 2, 1),
            outcome_available_date=date(2024, 5, 1),
            ticker=f"T{index}",
            component_scores={"quality": float(index), "valuation": float(10 - index)},
            forward_excess_return=float(index),
        )
        for index in range(1, 5)
    )
    observations.extend(
        CalibrationObservation(
            decision_date=date(2024, 3, 1),
            outcome_available_date=date(2024, 6, 1),
            ticker=f"T{index}",
            component_scores={"quality": float(index), "valuation": float(10 - index)},
            forward_excess_return=float(index),
        )
        for index in range(1, 5)
    )
    folds = make_expanding_folds(observations, min_train_dates=2, test_dates=1)
    report = run_walk_forward_calibration(
        observations=observations,
        baseline=_baseline(),
        candidates=(_baseline(),),
        folds=folds,
        policy=CalibrationPolicy(min_folds_for_promotion=1),
    )
    assert report.folds[0].training_ic is None
    assert not report.promote


def test_promotion_requires_repeated_out_of_sample_evidence() -> None:
    baseline = _baseline()
    candidate = WeightCandidate("quality_plus", {"quality": 0.64, "valuation": 0.36})
    policy = CalibrationPolicy(
        max_abs_weight_change=0.05,
        max_l1_drift=0.10,
        regularization_strength=0.0,
        min_folds_for_promotion=3,
        min_mean_oos_improvement=0.01,
        min_positive_fold_fraction=2.0 / 3.0,
        min_candidate_consensus_fraction=0.50,
    )
    observations: list[CalibrationObservation] = []
    months = [date(2023 + (index // 12), (index % 12) + 1, 1) for index in range(18)]
    for month_index, decision_date in enumerate(months):
        outcome_date = months[min(month_index + 1, len(months) - 1)]
        for ticker_index in range(1, 6):
            quality = float(ticker_index * 10)
            valuation = float((6 - ticker_index) * 10)
            forward = quality / 100.0
            observations.append(
                CalibrationObservation(
                    decision_date=decision_date,
                    outcome_available_date=outcome_date,
                    ticker=f"T{ticker_index}",
                    component_scores={"quality": quality, "valuation": valuation},
                    forward_excess_return=forward,
                )
            )
    folds = make_expanding_folds(observations, min_train_dates=6, test_dates=3, step_dates=3)
    report = run_walk_forward_calibration(
        observations=observations,
        baseline=baseline,
        candidates=(baseline, candidate),
        folds=folds,
        policy=policy,
    )
    assert len(report.folds) >= 3
    assert report.recommended_candidate_id in {None, "quality_plus"}
    if report.promote:
        assert report.mean_oos_improvement is not None
        assert report.mean_oos_improvement >= 0.01
