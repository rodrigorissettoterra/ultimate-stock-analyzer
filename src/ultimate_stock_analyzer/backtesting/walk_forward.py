from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date
from statistics import fmean, pstdev


@dataclass(frozen=True, slots=True)
class CalibrationObservation:
    decision_date: date
    outcome_available_date: date
    ticker: str
    component_scores: dict[str, float]
    forward_excess_return: float


@dataclass(frozen=True, slots=True)
class WeightCandidate:
    candidate_id: str
    weights: dict[str, float]


@dataclass(frozen=True, slots=True)
class WalkForwardFold:
    train_start: date
    train_end: date
    test_start: date
    test_end: date


@dataclass(frozen=True, slots=True)
class CalibrationPolicy:
    max_abs_weight_change: float = 0.05
    max_l1_drift: float = 0.15
    regularization_strength: float = 0.15
    min_folds_for_promotion: int = 3
    min_mean_oos_improvement: float = 0.02
    min_positive_fold_fraction: float = 2.0 / 3.0
    min_candidate_consensus_fraction: float = 0.50


@dataclass(frozen=True, slots=True)
class FoldEvaluation:
    fold: WalkForwardFold
    selected_candidate_id: str
    training_ic: float | None
    candidate_test_ic: float | None
    baseline_test_ic: float | None
    out_of_sample_improvement: float | None


@dataclass(frozen=True, slots=True)
class WalkForwardReport:
    folds: tuple[FoldEvaluation, ...]
    mean_oos_improvement: float | None
    positive_fold_fraction: float
    candidate_consensus_fraction: float
    recommended_candidate_id: str | None
    promote: bool


def _validate_weights(candidate: WeightCandidate, baseline: WeightCandidate, policy: CalibrationPolicy) -> None:
    if set(candidate.weights) != set(baseline.weights):
        raise ValueError("candidate component set must match baseline")
    if any(value < 0 for value in candidate.weights.values()):
        raise ValueError("weights cannot be negative")
    if abs(sum(candidate.weights.values()) - 1.0) > 1e-9:
        raise ValueError("candidate weights must sum to 1")
    abs_changes = [
        abs(candidate.weights[name] - baseline.weights[name]) for name in baseline.weights
    ]
    if max(abs_changes, default=0.0) > policy.max_abs_weight_change + 1e-12:
        raise ValueError("candidate exceeds maximum per-weight drift")
    if sum(abs_changes) > policy.max_l1_drift + 1e-12:
        raise ValueError("candidate exceeds maximum L1 drift")


def generate_local_candidates(
    baseline: WeightCandidate,
    *,
    step: float = 0.02,
    policy: CalibrationPolicy,
) -> tuple[WeightCandidate, ...]:
    if step <= 0:
        raise ValueError("step must be positive")
    candidates: list[WeightCandidate] = [baseline]
    names = sorted(baseline.weights)
    for donor in names:
        for receiver in names:
            if donor == receiver or baseline.weights[donor] < step:
                continue
            weights = dict(baseline.weights)
            weights[donor] -= step
            weights[receiver] += step
            candidate = WeightCandidate(f"shift_{donor}_to_{receiver}_{step:.3f}", weights)
            try:
                _validate_weights(candidate, baseline, policy)
            except ValueError:
                continue
            candidates.append(candidate)
    return tuple(candidates)


def make_expanding_folds(
    observations: list[CalibrationObservation],
    *,
    min_train_dates: int,
    test_dates: int,
    step_dates: int | None = None,
) -> tuple[WalkForwardFold, ...]:
    if min_train_dates < 2 or test_dates < 1:
        raise ValueError("invalid walk-forward window sizes")
    step = test_dates if step_dates is None else step_dates
    if step < 1:
        raise ValueError("step_dates must be positive")
    dates = sorted({row.decision_date for row in observations})
    folds: list[WalkForwardFold] = []
    train_count = min_train_dates
    while train_count + test_dates <= len(dates):
        folds.append(
            WalkForwardFold(
                train_start=dates[0],
                train_end=dates[train_count - 1],
                test_start=dates[train_count],
                test_end=dates[train_count + test_dates - 1],
            )
        )
        train_count += step
    return tuple(folds)


def _average_ranks(values: list[float]) -> list[float]:
    indexed = sorted(enumerate(values), key=lambda item: item[1])
    ranks = [0.0] * len(values)
    start = 0
    while start < len(indexed):
        end = start + 1
        while end < len(indexed) and indexed[end][1] == indexed[start][1]:
            end += 1
        average_rank = (start + 1 + end) / 2.0
        for position in range(start, end):
            ranks[indexed[position][0]] = average_rank
        start = end
    return ranks


def _correlation(left: list[float], right: list[float]) -> float | None:
    if len(left) < 3 or len(left) != len(right):
        return None
    left_std = pstdev(left)
    right_std = pstdev(right)
    if left_std == 0 or right_std == 0:
        return None
    left_mean = fmean(left)
    right_mean = fmean(right)
    covariance = fmean(
        (x_value - left_mean) * (y_value - right_mean)
        for x_value, y_value in zip(left, right, strict=True)
    )
    return covariance / (left_std * right_std)


def cross_sectional_information_coefficient(
    observations: list[CalibrationObservation],
    candidate: WeightCandidate,
) -> float | None:
    grouped: dict[date, list[CalibrationObservation]] = defaultdict(list)
    for row in observations:
        grouped[row.decision_date].append(row)

    correlations: list[float] = []
    for rows in grouped.values():
        scores: list[float] = []
        outcomes: list[float] = []
        for row in rows:
            if not all(name in row.component_scores for name in candidate.weights):
                continue
            score = sum(
                row.component_scores[name] * weight for name, weight in candidate.weights.items()
            )
            scores.append(score)
            outcomes.append(row.forward_excess_return)
        correlation = _correlation(_average_ranks(scores), _average_ranks(outcomes))
        if correlation is not None:
            correlations.append(correlation)
    return fmean(correlations) if correlations else None


def _l1_distance(candidate: WeightCandidate, baseline: WeightCandidate) -> float:
    return sum(abs(candidate.weights[name] - baseline.weights[name]) for name in baseline.weights)


def _training_rows(
    observations: list[CalibrationObservation],
    fold: WalkForwardFold,
) -> list[CalibrationObservation]:
    return [
        row
        for row in observations
        if fold.train_start <= row.decision_date <= fold.train_end
        and row.outcome_available_date < fold.test_start
    ]


def _test_rows(
    observations: list[CalibrationObservation],
    fold: WalkForwardFold,
) -> list[CalibrationObservation]:
    return [row for row in observations if fold.test_start <= row.decision_date <= fold.test_end]


def run_walk_forward_calibration(
    *,
    observations: list[CalibrationObservation],
    baseline: WeightCandidate,
    candidates: tuple[WeightCandidate, ...],
    folds: tuple[WalkForwardFold, ...],
    policy: CalibrationPolicy,
) -> WalkForwardReport:
    _validate_weights(baseline, baseline, policy)
    candidate_map = {candidate.candidate_id: candidate for candidate in candidates}
    if baseline.candidate_id not in candidate_map:
        raise ValueError("candidate set must include baseline")
    for candidate in candidates:
        _validate_weights(candidate, baseline, policy)

    evaluations: list[FoldEvaluation] = []
    for fold in folds:
        training = _training_rows(observations, fold)
        testing = _test_rows(observations, fold)
        ranked_candidates: list[tuple[float, float, str, float | None]] = []
        for candidate in candidates:
            training_ic = cross_sectional_information_coefficient(training, candidate)
            if training_ic is None:
                continue
            distance = _l1_distance(candidate, baseline)
            objective = training_ic - policy.regularization_strength * distance
            ranked_candidates.append((objective, -distance, candidate.candidate_id, training_ic))
        if not ranked_candidates:
            selected = baseline
            training_ic = None
        else:
            _, _, selected_id, training_ic = max(ranked_candidates)
            selected = candidate_map[selected_id]

        candidate_test_ic = cross_sectional_information_coefficient(testing, selected)
        baseline_test_ic = cross_sectional_information_coefficient(testing, baseline)
        improvement = (
            candidate_test_ic - baseline_test_ic
            if candidate_test_ic is not None and baseline_test_ic is not None
            else None
        )
        evaluations.append(
            FoldEvaluation(
                fold=fold,
                selected_candidate_id=selected.candidate_id,
                training_ic=training_ic,
                candidate_test_ic=candidate_test_ic,
                baseline_test_ic=baseline_test_ic,
                out_of_sample_improvement=improvement,
            )
        )

    valid_improvements = [
        row.out_of_sample_improvement
        for row in evaluations
        if row.out_of_sample_improvement is not None
    ]
    mean_improvement = fmean(valid_improvements) if valid_improvements else None
    positive_fraction = (
        sum(value > 0 for value in valid_improvements) / len(valid_improvements)
        if valid_improvements
        else 0.0
    )
    selected_counts = Counter(row.selected_candidate_id for row in evaluations)
    most_common = selected_counts.most_common(1)
    consensus_id = most_common[0][0] if most_common else None
    consensus_fraction = most_common[0][1] / len(evaluations) if evaluations and most_common else 0.0
    promote = (
        len(valid_improvements) >= policy.min_folds_for_promotion
        and mean_improvement is not None
        and mean_improvement >= policy.min_mean_oos_improvement
        and positive_fraction >= policy.min_positive_fold_fraction
        and consensus_fraction >= policy.min_candidate_consensus_fraction
        and consensus_id is not None
        and consensus_id != baseline.candidate_id
    )
    return WalkForwardReport(
        folds=tuple(evaluations),
        mean_oos_improvement=mean_improvement,
        positive_fold_fraction=positive_fraction,
        candidate_consensus_fraction=consensus_fraction,
        recommended_candidate_id=consensus_id if promote else None,
        promote=promote,
    )
