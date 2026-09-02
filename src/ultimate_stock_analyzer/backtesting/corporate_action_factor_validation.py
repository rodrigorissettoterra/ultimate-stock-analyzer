from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from typing import Any

from ultimate_stock_analyzer.collectors.b3_corporate_actions import (
    B3StockActionContractRecord,
)
from ultimate_stock_analyzer.market.prices import PriceBar

DIRECT_FACTOR = "DIRECT_FACTOR"
FACTOR_PERCENT = "FACTOR_PERCENT"
ONE_PLUS_FACTOR_PERCENT = "ONE_PLUS_FACTOR_PERCENT"
INVERSE_FACTOR = "INVERSE_FACTOR"

MISSING_EXACT_COM_PRICE = "MISSING_EXACT_COM_PRICE"
MISSING_EX_PRICE = "MISSING_EX_PRICE"
EVENT_ISIN_MISMATCH = "EVENT_ISIN_MISMATCH"
INVALID_EVENT_FACTOR = "INVALID_EVENT_FACTOR"
AMBIGUOUS_FACTOR_TRANSFORM = "AMBIGUOUS_FACTOR_TRANSFORM"
EMPIRICALLY_CONSISTENT = "EMPIRICALLY_CONSISTENT"


@dataclass(frozen=True, slots=True)
class FactorTransformCandidate:
    name: str
    ratio_new_per_old: float
    open_relative_error: float
    close_relative_error: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class CorporateActionFactorEvidence:
    issuing_company: str
    ticker: str
    label: str
    factor: float | None
    event_isin: str | None
    com_date: str | None
    ex_trade_date: str | None
    pre_event_isin: str | None
    post_event_isin: str | None
    pre_close: float | None
    post_open: float | None
    post_close: float | None
    observed_ratio_close_to_open: float | None
    observed_ratio_close_to_close: float | None
    candidates: tuple[FactorTransformCandidate, ...]
    best_candidate: str | None
    best_open_relative_error: float | None
    second_best_open_relative_error: float | None
    empirically_consistent: bool
    status: str
    blockers: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["candidates"] = [candidate.to_dict() for candidate in self.candidates]
        return payload


@dataclass(frozen=True, slots=True)
class LabelFactorSummary:
    label: str
    identity_matched_event_count: int
    empirically_consistent_event_count: int
    issuing_company_count: int
    candidate_counts: dict[str, int]
    dominant_candidate: str | None
    promotion_ready: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def validate_corporate_action_factor(
    *,
    issuing_company: str,
    ticker: str,
    event: B3StockActionContractRecord,
    bars: Iterable[PriceBar],
    max_open_relative_error: float = 0.15,
    min_second_best_error_margin: float = 0.10,
) -> CorporateActionFactorEvidence:
    blockers: list[str] = []
    normalized_ticker = ticker.strip().upper()
    event_date = event.last_date_prior
    factor = event.factor
    ticker_bars = sorted(
        (bar for bar in bars if bar.ticker.upper() == normalized_ticker),
        key=lambda bar: bar.trade_date,
    )

    if factor is None or factor <= 0:
        blockers.append(INVALID_EVENT_FACTOR)
    if event_date is None:
        blockers.append(MISSING_EXACT_COM_PRICE)

    pre_bar: PriceBar | None = None
    post_bar: PriceBar | None = None
    if event_date is not None:
        pre_bar = next((bar for bar in ticker_bars if bar.trade_date == event_date), None)
        post_candidates = [bar for bar in ticker_bars if bar.trade_date > event_date]
        post_bar = min(post_candidates, key=lambda bar: bar.trade_date) if post_candidates else None
        if pre_bar is None:
            blockers.append(MISSING_EXACT_COM_PRICE)
        if post_bar is None:
            blockers.append(MISSING_EX_PRICE)

    if pre_bar is not None and post_bar is not None and event.isin_code is not None:
        observed_isins = {isin for isin in (pre_bar.isin, post_bar.isin) if isin is not None}
        if observed_isins and observed_isins != {event.isin_code}:
            blockers.append(EVENT_ISIN_MISMATCH)

    if blockers or pre_bar is None or post_bar is None or factor is None or factor <= 0:
        return _blocked_evidence(
            issuing_company=issuing_company,
            ticker=normalized_ticker,
            event=event,
            pre_bar=pre_bar,
            post_bar=post_bar,
            blockers=blockers,
        )

    observed_open_ratio = pre_bar.close / post_bar.open
    observed_close_ratio = pre_bar.close / post_bar.close
    candidate_ratios = (
        (DIRECT_FACTOR, factor),
        (FACTOR_PERCENT, factor / 100.0),
        (ONE_PLUS_FACTOR_PERCENT, 1.0 + factor / 100.0),
        (INVERSE_FACTOR, 1.0 / factor),
    )
    candidates = tuple(
        FactorTransformCandidate(
            name=name,
            ratio_new_per_old=ratio,
            open_relative_error=_relative_error(ratio, observed_open_ratio),
            close_relative_error=_relative_error(ratio, observed_close_ratio),
        )
        for name, ratio in candidate_ratios
        if ratio > 0
    )
    ordered = sorted(candidates, key=lambda candidate: (candidate.open_relative_error, candidate.name))
    best = ordered[0]
    second = ordered[1] if len(ordered) > 1 else None
    second_error = second.open_relative_error if second is not None else None
    margin = second_error - best.open_relative_error if second_error is not None else float("inf")
    consistent = (
        best.open_relative_error <= max_open_relative_error
        and margin >= min_second_best_error_margin
    )
    status = EMPIRICALLY_CONSISTENT if consistent else AMBIGUOUS_FACTOR_TRANSFORM
    diagnostic_blockers = () if consistent else (AMBIGUOUS_FACTOR_TRANSFORM,)

    return CorporateActionFactorEvidence(
        issuing_company=issuing_company.strip().upper(),
        ticker=normalized_ticker,
        label=event.normalized_label,
        factor=factor,
        event_isin=event.isin_code,
        com_date=event_date.isoformat(),
        ex_trade_date=post_bar.trade_date.isoformat(),
        pre_event_isin=pre_bar.isin,
        post_event_isin=post_bar.isin,
        pre_close=pre_bar.close,
        post_open=post_bar.open,
        post_close=post_bar.close,
        observed_ratio_close_to_open=observed_open_ratio,
        observed_ratio_close_to_close=observed_close_ratio,
        candidates=candidates,
        best_candidate=best.name,
        best_open_relative_error=best.open_relative_error,
        second_best_open_relative_error=second_error,
        empirically_consistent=consistent,
        status=status,
        blockers=diagnostic_blockers,
    )


def summarize_factor_evidence(
    evidence: Iterable[CorporateActionFactorEvidence],
    *,
    min_events_per_label: int = 2,
    min_issuers_per_label: int = 2,
) -> tuple[LabelFactorSummary, ...]:
    grouped: dict[str, list[CorporateActionFactorEvidence]] = defaultdict(list)
    for item in evidence:
        grouped[item.label].append(item)

    summaries: list[LabelFactorSummary] = []
    for label, items in sorted(grouped.items()):
        identity_matched = [
            item for item in items if EVENT_ISIN_MISMATCH not in item.blockers
        ]
        consistent = [item for item in identity_matched if item.empirically_consistent]
        counts = Counter(
            item.best_candidate for item in consistent if item.best_candidate is not None
        )
        dominant_candidate: str | None = None
        if counts:
            candidate, count = counts.most_common(1)[0]
            if count == len(consistent):
                dominant_candidate = candidate
        issuers = {item.issuing_company for item in consistent}
        promotion_ready = (
            len(consistent) >= min_events_per_label
            and len(issuers) >= min_issuers_per_label
            and dominant_candidate is not None
        )
        summaries.append(
            LabelFactorSummary(
                label=label,
                identity_matched_event_count=len(identity_matched),
                empirically_consistent_event_count=len(consistent),
                issuing_company_count=len(issuers),
                candidate_counts=dict(sorted(counts.items())),
                dominant_candidate=dominant_candidate,
                promotion_ready=promotion_ready,
            )
        )
    return tuple(summaries)


def _blocked_evidence(
    *,
    issuing_company: str,
    ticker: str,
    event: B3StockActionContractRecord,
    pre_bar: PriceBar | None,
    post_bar: PriceBar | None,
    blockers: list[str],
) -> CorporateActionFactorEvidence:
    return CorporateActionFactorEvidence(
        issuing_company=issuing_company.strip().upper(),
        ticker=ticker,
        label=event.normalized_label,
        factor=event.factor,
        event_isin=event.isin_code,
        com_date=event.last_date_prior.isoformat() if event.last_date_prior is not None else None,
        ex_trade_date=post_bar.trade_date.isoformat() if post_bar is not None else None,
        pre_event_isin=pre_bar.isin if pre_bar is not None else None,
        post_event_isin=post_bar.isin if post_bar is not None else None,
        pre_close=pre_bar.close if pre_bar is not None else None,
        post_open=post_bar.open if post_bar is not None else None,
        post_close=post_bar.close if post_bar is not None else None,
        observed_ratio_close_to_open=None,
        observed_ratio_close_to_close=None,
        candidates=(),
        best_candidate=None,
        best_open_relative_error=None,
        second_best_open_relative_error=None,
        empirically_consistent=False,
        status=blockers[0] if blockers else AMBIGUOUS_FACTOR_TRANSFORM,
        blockers=tuple(sorted(set(blockers))),
    )


def _relative_error(candidate: float, observed: float) -> float:
    if observed <= 0:
        return float("inf")
    return abs(candidate - observed) / observed
