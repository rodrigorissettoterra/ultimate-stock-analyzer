from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

from ultimate_stock_analyzer.backtesting.corporate_action_factor_validation import (
    DIRECT_FACTOR,
    ONE_PLUS_FACTOR_PERCENT,
    CorporateActionFactorEvidence,
    validate_corporate_action_factor,
)
from ultimate_stock_analyzer.backtesting.models import ShareAction
from ultimate_stock_analyzer.collectors.b3_corporate_actions import (
    SUPPORTED_LABEL_FACTOR_CONFLICT,
    B3StockActionContractRecord,
)
from ultimate_stock_analyzer.market.prices import PriceBar

CONVERTED_EMPIRICALLY_VALIDATED_LABEL = "CONVERTED_EMPIRICALLY_VALIDATED_LABEL"
UNSUPPORTED_CONVERSION_LABEL = "UNSUPPORTED_CONVERSION_LABEL"
INVALID_CONVERSION_FACTOR = "INVALID_CONVERSION_FACTOR"
MISSING_CONVERSION_COM_DATE = "MISSING_CONVERSION_COM_DATE"
OFFICIAL_COMPLETE_FACTOR_CONFLICT = "OFFICIAL_COMPLETE_FACTOR_CONFLICT"
EMPIRICAL_EVENT_VALIDATION_FAILED = "EMPIRICAL_EVENT_VALIDATION_FAILED"
EMPIRICAL_FORMULA_MISMATCH = "EMPIRICAL_FORMULA_MISMATCH"

_LABEL_CANDIDATES = {
    "BONIFICACAO": ONE_PLUS_FACTOR_PERCENT,
    "DESDOBRAMENTO": ONE_PLUS_FACTOR_PERCENT,
    "GRUPAMENTO": DIRECT_FACTOR,
}


@dataclass(frozen=True, slots=True)
class B3ShareActionConversion:
    ticker: str
    label: str
    factor: float | None
    event_isin: str | None
    com_date: date | None
    ex_date: date | None
    expected_candidate: str | None
    ratio_new_per_old: float | None
    status: str
    blockers: tuple[str, ...]
    evidence: CorporateActionFactorEvidence | None
    action: ShareAction | None

    @property
    def converted(self) -> bool:
        return self.action is not None and not self.blockers

    def to_dict(self) -> dict[str, Any]:
        return {
            "ticker": self.ticker,
            "label": self.label,
            "factor": self.factor,
            "event_isin": self.event_isin,
            "com_date": self.com_date.isoformat() if self.com_date is not None else None,
            "ex_date": self.ex_date.isoformat() if self.ex_date is not None else None,
            "expected_candidate": self.expected_candidate,
            "ratio_new_per_old": self.ratio_new_per_old,
            "status": self.status,
            "blockers": list(self.blockers),
            "evidence": self.evidence.to_dict() if self.evidence is not None else None,
            "action": (
                {
                    "ticker": self.action.ticker,
                    "ex_date": self.action.ex_date.isoformat(),
                    "ratio_new_per_old": self.action.ratio_new_per_old,
                }
                if self.action is not None
                else None
            ),
        }


def expected_b3_share_ratio(label: str, factor: float) -> tuple[str, float] | None:
    normalized_label = label.strip().upper()
    candidate = _LABEL_CANDIDATES.get(normalized_label)
    if candidate is None or factor <= 0:
        return None
    if candidate == ONE_PLUS_FACTOR_PERCENT:
        return candidate, 1.0 + factor / 100.0
    if candidate == DIRECT_FACTOR:
        return candidate, factor
    raise RuntimeError(f"unsupported validated candidate {candidate}")


def convert_b3_stock_action(
    *,
    issuing_company: str,
    ticker: str,
    event: B3StockActionContractRecord,
    bars: list[PriceBar],
    max_open_relative_error: float = 0.15,
    min_second_best_error_margin: float = 0.10,
    ratio_tolerance: float = 1e-9,
) -> B3ShareActionConversion:
    normalized_ticker = ticker.strip().upper()
    label = event.normalized_label
    factor = event.factor

    if label not in _LABEL_CANDIDATES:
        return _blocked(
            ticker=normalized_ticker,
            event=event,
            status=UNSUPPORTED_CONVERSION_LABEL,
            blockers=(UNSUPPORTED_CONVERSION_LABEL,),
        )
    if factor is None or factor <= 0:
        return _blocked(
            ticker=normalized_ticker,
            event=event,
            status=INVALID_CONVERSION_FACTOR,
            blockers=(INVALID_CONVERSION_FACTOR,),
        )
    if event.last_date_prior is None:
        return _blocked(
            ticker=normalized_ticker,
            event=event,
            status=MISSING_CONVERSION_COM_DATE,
            blockers=(MISSING_CONVERSION_COM_DATE,),
        )

    expected = expected_b3_share_ratio(label, factor)
    assert expected is not None
    expected_candidate, expected_ratio = expected

    if event.complete_factor is not None:
        if event.conversion_status == SUPPORTED_LABEL_FACTOR_CONFLICT:
            return _blocked(
                ticker=normalized_ticker,
                event=event,
                status=OFFICIAL_COMPLETE_FACTOR_CONFLICT,
                blockers=(OFFICIAL_COMPLETE_FACTOR_CONFLICT,),
                expected_candidate=expected_candidate,
                ratio_new_per_old=expected_ratio,
            )
        if (
            event.ratio_new_per_old is None
            or abs(event.ratio_new_per_old - expected_ratio) > ratio_tolerance
        ):
            return _blocked(
                ticker=normalized_ticker,
                event=event,
                status=OFFICIAL_COMPLETE_FACTOR_CONFLICT,
                blockers=(OFFICIAL_COMPLETE_FACTOR_CONFLICT,),
                expected_candidate=expected_candidate,
                ratio_new_per_old=expected_ratio,
            )

    evidence = validate_corporate_action_factor(
        issuing_company=issuing_company,
        ticker=normalized_ticker,
        event=event,
        bars=bars,
        max_open_relative_error=max_open_relative_error,
        min_second_best_error_margin=min_second_best_error_margin,
    )
    if not evidence.empirically_consistent or evidence.ex_trade_date is None:
        blockers = tuple(sorted(set((*evidence.blockers, EMPIRICAL_EVENT_VALIDATION_FAILED))))
        return _blocked(
            ticker=normalized_ticker,
            event=event,
            status=EMPIRICAL_EVENT_VALIDATION_FAILED,
            blockers=blockers,
            expected_candidate=expected_candidate,
            ratio_new_per_old=expected_ratio,
            evidence=evidence,
        )
    if evidence.best_candidate != expected_candidate:
        return _blocked(
            ticker=normalized_ticker,
            event=event,
            status=EMPIRICAL_FORMULA_MISMATCH,
            blockers=(EMPIRICAL_FORMULA_MISMATCH,),
            expected_candidate=expected_candidate,
            ratio_new_per_old=expected_ratio,
            evidence=evidence,
        )

    ex_date = date.fromisoformat(evidence.ex_trade_date)
    action = ShareAction(
        ticker=normalized_ticker,
        ex_date=ex_date,
        ratio_new_per_old=expected_ratio,
    )
    return B3ShareActionConversion(
        ticker=normalized_ticker,
        label=label,
        factor=factor,
        event_isin=event.isin_code,
        com_date=event.last_date_prior,
        ex_date=ex_date,
        expected_candidate=expected_candidate,
        ratio_new_per_old=expected_ratio,
        status=CONVERTED_EMPIRICALLY_VALIDATED_LABEL,
        blockers=(),
        evidence=evidence,
        action=action,
    )


def _blocked(
    *,
    ticker: str,
    event: B3StockActionContractRecord,
    status: str,
    blockers: tuple[str, ...],
    expected_candidate: str | None = None,
    ratio_new_per_old: float | None = None,
    evidence: CorporateActionFactorEvidence | None = None,
) -> B3ShareActionConversion:
    ex_date = (
        date.fromisoformat(evidence.ex_trade_date)
        if evidence is not None and evidence.ex_trade_date is not None
        else None
    )
    return B3ShareActionConversion(
        ticker=ticker,
        label=event.normalized_label,
        factor=event.factor,
        event_isin=event.isin_code,
        com_date=event.last_date_prior,
        ex_date=ex_date,
        expected_candidate=expected_candidate,
        ratio_new_per_old=ratio_new_per_old,
        status=status,
        blockers=tuple(sorted(set(blockers))),
        evidence=evidence,
        action=None,
    )
