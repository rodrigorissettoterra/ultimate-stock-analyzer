from __future__ import annotations

from collections import defaultdict
from datetime import UTC, date, datetime, time

from ultimate_stock_analyzer.backtesting.models import ScoreSnapshot, UniverseMembership


def decision_cutoff(as_of: date) -> datetime:
    """Conservative end-of-day cutoff used only for already-published evidence."""
    return datetime.combine(as_of, time.max, tzinfo=UTC)


def eligible_tickers(memberships: list[UniverseMembership], as_of: date) -> set[str]:
    return {membership.ticker for membership in memberships if membership.contains(as_of)}


def latest_visible_scores(
    snapshots: list[ScoreSnapshot],
    *,
    as_of: date,
    memberships: list[UniverseMembership],
) -> dict[str, ScoreSnapshot]:
    """Return the newest score that was actually available on the historical decision date.

    Later restatements/recalculations for the same reference period are invisible until their
    `available_at` timestamp. Delisted companies remain eligible while their historical membership
    interval says they were listed, avoiding present-day survivorship filtering.
    """
    cutoff = decision_cutoff(as_of)
    universe = eligible_tickers(memberships, as_of)
    candidates: dict[str, list[ScoreSnapshot]] = defaultdict(list)
    for snapshot in snapshots:
        visible_time = snapshot.available_at
        if visible_time.tzinfo is None:
            visible_time = visible_time.replace(tzinfo=UTC)
        if (
            snapshot.ticker in universe
            and snapshot.reference_date <= as_of
            and visible_time <= cutoff
            and snapshot.rankable
        ):
            candidates[snapshot.ticker].append(snapshot)

    result: dict[str, ScoreSnapshot] = {}
    for ticker, rows in candidates.items():
        result[ticker] = max(
            rows,
            key=lambda item: (
                item.reference_date,
                item.available_at.replace(tzinfo=UTC)
                if item.available_at.tzinfo is None
                else item.available_at,
            ),
        )
    return result


def rank_visible_scores(
    snapshots: list[ScoreSnapshot],
    *,
    as_of: date,
    memberships: list[UniverseMembership],
    top_n: int,
    min_score: float = 0.0,
) -> tuple[ScoreSnapshot, ...]:
    visible = latest_visible_scores(snapshots, as_of=as_of, memberships=memberships)
    ranked = sorted(
        (row for row in visible.values() if row.investment_score >= min_score),
        key=lambda row: (-row.investment_score, row.ticker),
    )
    return tuple(ranked[:top_n])
