from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from typing import Any

from ultimate_stock_analyzer.backtesting.models import CashDistribution
from ultimate_stock_analyzer.collectors.b3_corporate_actions import B3SubscriptionContractRecord
from ultimate_stock_analyzer.market.prices import PriceBar

SUBSCRIPTION_RIGHT_CONVERTED = "SUBSCRIPTION_RIGHT_CONVERTED"
SUBSCRIPTION_RIGHT_PERCENTAGE_INVALID = "SUBSCRIPTION_RIGHT_PERCENTAGE_INVALID"
SUBSCRIPTION_RIGHT_PRICE_INVALID = "SUBSCRIPTION_RIGHT_PRICE_INVALID"
SUBSCRIPTION_RIGHT_COM_DATE_MISSING = "SUBSCRIPTION_RIGHT_COM_DATE_MISSING"
SUBSCRIPTION_RIGHT_COM_BAR_MISSING = "SUBSCRIPTION_RIGHT_COM_BAR_MISSING"
SUBSCRIPTION_RIGHT_EX_BAR_MISSING = "SUBSCRIPTION_RIGHT_EX_BAR_MISSING"
SUBSCRIPTION_RIGHT_IDENTITY_INSUFFICIENT = "SUBSCRIPTION_RIGHT_IDENTITY_INSUFFICIENT"
SUBSCRIPTION_RIGHT_ISIN_MISMATCH = "SUBSCRIPTION_RIGHT_ISIN_MISMATCH"
SUBSCRIPTION_RIGHT_AVAILABILITY_UNKNOWN = "SUBSCRIPTION_RIGHT_AVAILABILITY_UNKNOWN"
SUBSCRIPTION_RIGHT_AVAILABLE_AFTER_EX = "SUBSCRIPTION_RIGHT_AVAILABLE_AFTER_EX"


@dataclass(frozen=True, slots=True)
class B3SubscriptionRightConversion:
    ticker: str
    percentage: float | None
    subscription_price: float | None
    event_asset_issued: str | None
    event_isin: str | None
    com_date: date | None
    ex_date: date | None
    com_close: float | None
    subscription_ratio: float | None
    value_reference_per_share: float | None
    available_from: datetime | None
    point_in_time_eligible: bool
    status: str
    blockers: tuple[str, ...]
    distribution: CashDistribution | None

    @property
    def converted(self) -> bool:
        return self.distribution is not None and not self.blockers

    def to_dict(self) -> dict[str, Any]:
        return {
            "ticker": self.ticker,
            "percentage": self.percentage,
            "subscription_price": self.subscription_price,
            "event_asset_issued": self.event_asset_issued,
            "event_isin": self.event_isin,
            "com_date": self.com_date.isoformat() if self.com_date is not None else None,
            "ex_date": self.ex_date.isoformat() if self.ex_date is not None else None,
            "com_close": self.com_close,
            "subscription_ratio": self.subscription_ratio,
            "value_reference_per_share": self.value_reference_per_share,
            "available_from": (
                self.available_from.isoformat() if self.available_from is not None else None
            ),
            "point_in_time_eligible": self.point_in_time_eligible,
            "status": self.status,
            "blockers": list(self.blockers),
            "distribution": (
                {
                    "ticker": self.distribution.ticker,
                    "ex_date": self.distribution.ex_date.isoformat(),
                    "amount_per_share": self.distribution.amount_per_share,
                }
                if self.distribution is not None
                else None
            ),
        }


def convert_b3_subscription_right(
    *,
    ticker: str,
    event: B3SubscriptionContractRecord,
    bars: list[PriceBar],
) -> B3SubscriptionRightConversion:
    """Value a same-security subscription right using the official B3 reference formula.

    The conversion represents the economic value of the right received by the existing
    shareholder. It does not assume that the shareholder exercises the right or contributes
    new capital.
    """
    normalized_ticker = _normalize(ticker)
    if normalized_ticker is None:
        raise ValueError("ticker must not be blank")

    percentage = event.percentage
    subscription_price = event.price_unit
    if percentage is None or percentage <= 0:
        return _blocked(
            ticker=normalized_ticker,
            event=event,
            status=SUBSCRIPTION_RIGHT_PERCENTAGE_INVALID,
        )
    if subscription_price is None or subscription_price < 0:
        return _blocked(
            ticker=normalized_ticker,
            event=event,
            status=SUBSCRIPTION_RIGHT_PRICE_INVALID,
        )
    if event.last_date_prior is None:
        return _blocked(
            ticker=normalized_ticker,
            event=event,
            status=SUBSCRIPTION_RIGHT_COM_DATE_MISSING,
        )

    ticker_bars = sorted(
        (bar for bar in bars if bar.ticker.upper() == normalized_ticker),
        key=lambda item: item.trade_date,
    )
    target_isins = {
        normalized
        for bar in ticker_bars
        for normalized in [_normalize(bar.isin)]
        if normalized is not None
    }
    identity_status = _identity_status(
        event=event,
        ticker=normalized_ticker,
        target_isins=target_isins,
    )
    if identity_status is not None:
        return _blocked(
            ticker=normalized_ticker,
            event=event,
            status=identity_status,
        )

    com_bar = next(
        (bar for bar in ticker_bars if bar.trade_date == event.last_date_prior),
        None,
    )
    if com_bar is None:
        return _blocked(
            ticker=normalized_ticker,
            event=event,
            status=SUBSCRIPTION_RIGHT_COM_BAR_MISSING,
        )
    ex_bar = next(
        (bar for bar in ticker_bars if bar.trade_date > event.last_date_prior),
        None,
    )
    if ex_bar is None:
        return _blocked(
            ticker=normalized_ticker,
            event=event,
            status=SUBSCRIPTION_RIGHT_EX_BAR_MISSING,
            com_close=com_bar.close,
        )

    bar_isins = {
        normalized
        for bar in (com_bar, ex_bar)
        for normalized in [_normalize(bar.isin)]
        if normalized is not None
    }
    if len(bar_isins) != 1:
        return _blocked(
            ticker=normalized_ticker,
            event=event,
            status=SUBSCRIPTION_RIGHT_IDENTITY_INSUFFICIENT,
            ex_date=ex_bar.trade_date,
            com_close=com_bar.close,
        )
    asserted_isins = {
        value
        for value in (
            _event_asset_isin(event.asset_issued, normalized_ticker),
            _normalize(event.isin_code),
        )
        if value is not None
    }
    if asserted_isins and asserted_isins != bar_isins:
        return _blocked(
            ticker=normalized_ticker,
            event=event,
            status=SUBSCRIPTION_RIGHT_ISIN_MISMATCH,
            ex_date=ex_bar.trade_date,
            com_close=com_bar.close,
        )

    available_from = _conservative_availability(event.approved_on)
    if available_from is None:
        return _blocked(
            ticker=normalized_ticker,
            event=event,
            status=SUBSCRIPTION_RIGHT_AVAILABILITY_UNKNOWN,
            ex_date=ex_bar.trade_date,
            com_close=com_bar.close,
        )
    if available_from.date() > ex_bar.trade_date:
        return _blocked(
            ticker=normalized_ticker,
            event=event,
            status=SUBSCRIPTION_RIGHT_AVAILABLE_AFTER_EX,
            ex_date=ex_bar.trade_date,
            com_close=com_bar.close,
            available_from=available_from,
        )

    subscription_ratio = percentage / 100.0
    intrinsic_spread = max(com_bar.close - subscription_price, 0.0)
    value_reference = subscription_ratio / (1.0 + subscription_ratio) * intrinsic_spread
    distribution = CashDistribution(
        ticker=normalized_ticker,
        ex_date=ex_bar.trade_date,
        amount_per_share=value_reference,
    )
    return B3SubscriptionRightConversion(
        ticker=normalized_ticker,
        percentage=percentage,
        subscription_price=subscription_price,
        event_asset_issued=event.asset_issued,
        event_isin=event.isin_code,
        com_date=event.last_date_prior,
        ex_date=ex_bar.trade_date,
        com_close=com_bar.close,
        subscription_ratio=subscription_ratio,
        value_reference_per_share=value_reference,
        available_from=available_from,
        point_in_time_eligible=True,
        status=SUBSCRIPTION_RIGHT_CONVERTED,
        blockers=(),
        distribution=distribution,
    )


def _identity_status(
    *,
    event: B3SubscriptionContractRecord,
    ticker: str,
    target_isins: set[str],
) -> str | None:
    if not target_isins:
        return SUBSCRIPTION_RIGHT_IDENTITY_INSUFFICIENT

    asset = _normalize(event.asset_issued)
    event_isin = _normalize(event.isin_code)
    if asset is None and event_isin is None:
        return SUBSCRIPTION_RIGHT_IDENTITY_INSUFFICIENT

    matches = False
    if asset is not None:
        if asset == ticker or asset in target_isins:
            matches = True
        else:
            return SUBSCRIPTION_RIGHT_ISIN_MISMATCH
    if event_isin is not None:
        if event_isin in target_isins:
            matches = True
        else:
            return SUBSCRIPTION_RIGHT_ISIN_MISMATCH
    return None if matches else SUBSCRIPTION_RIGHT_IDENTITY_INSUFFICIENT


def _blocked(
    *,
    ticker: str,
    event: B3SubscriptionContractRecord,
    status: str,
    ex_date: date | None = None,
    com_close: float | None = None,
    available_from: datetime | None = None,
) -> B3SubscriptionRightConversion:
    percentage = event.percentage
    ratio = percentage / 100.0 if percentage is not None and percentage > 0 else None
    return B3SubscriptionRightConversion(
        ticker=ticker,
        percentage=percentage,
        subscription_price=event.price_unit,
        event_asset_issued=event.asset_issued,
        event_isin=event.isin_code,
        com_date=event.last_date_prior,
        ex_date=ex_date,
        com_close=com_close,
        subscription_ratio=ratio,
        value_reference_per_share=None,
        available_from=available_from,
        point_in_time_eligible=False,
        status=status,
        blockers=(status,),
        distribution=None,
    )


def _conservative_availability(approved_on: date | None) -> datetime | None:
    if approved_on is None:
        return None
    next_day = approved_on + timedelta(days=1)
    return datetime.combine(next_day, time.min, tzinfo=UTC)


def _event_asset_isin(value: str | None, ticker: str) -> str | None:
    normalized = _normalize(value)
    if normalized is None or normalized == ticker:
        return None
    return normalized if _looks_like_isin(normalized) else None


def _looks_like_isin(value: str) -> bool:
    return len(value) == 12 and value[:2].isalpha() and value.isalnum()


def _normalize(value: object | None) -> str | None:
    if value is None:
        return None
    normalized = "".join(character for character in str(value).upper() if character.isalnum())
    return normalized or None
