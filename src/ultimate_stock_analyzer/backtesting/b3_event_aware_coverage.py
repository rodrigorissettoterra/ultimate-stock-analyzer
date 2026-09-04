from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any

from ultimate_stock_analyzer.backtesting.b3_share_action_conversion import (
    B3ShareActionConversion,
    convert_b3_stock_action,
)
from ultimate_stock_analyzer.backtesting.b3_subscription_right_conversion import (
    SUBSCRIPTION_RIGHT_IDENTITY_INSUFFICIENT,
    SUBSCRIPTION_RIGHT_ISIN_MISMATCH,
    B3SubscriptionRightConversion,
    convert_b3_subscription_right,
)
from ultimate_stock_analyzer.backtesting.models import CashDistribution
from ultimate_stock_analyzer.collectors.b3_corporate_actions import (
    B3CorporateActionsContractAuditor,
    B3StockActionContractRecord,
    B3SubscriptionContractRecord,
)
from ultimate_stock_analyzer.collectors.b3_dividends import B3DividendCollector
from ultimate_stock_analyzer.dividends.regularity import DividendPayment
from ultimate_stock_analyzer.market.prices import PriceBar

CASH_DISTRIBUTION_CONVERTED = "CASH_DISTRIBUTION_CONVERTED"
CASH_DISTRIBUTION_SCOPE_MISMATCH = "CASH_DISTRIBUTION_SCOPE_MISMATCH"
CASH_DISTRIBUTION_DATE_BASIS_UNSUPPORTED = "CASH_DISTRIBUTION_DATE_BASIS_UNSUPPORTED"
CASH_DISTRIBUTION_KIND_UNSUPPORTED = "CASH_DISTRIBUTION_KIND_UNSUPPORTED"
CASH_DISTRIBUTION_AMOUNT_INVALID = "CASH_DISTRIBUTION_AMOUNT_INVALID"
CASH_DISTRIBUTION_COM_BAR_MISSING = "CASH_DISTRIBUTION_COM_BAR_MISSING"
CASH_DISTRIBUTION_EX_BAR_MISSING = "CASH_DISTRIBUTION_EX_BAR_MISSING"
CASH_DISTRIBUTION_ISIN_MISMATCH = "CASH_DISTRIBUTION_ISIN_MISMATCH"
CASH_DISTRIBUTION_IDENTITY_INSUFFICIENT = "CASH_DISTRIBUTION_IDENTITY_INSUFFICIENT"
CASH_DISTRIBUTION_AVAILABILITY_UNKNOWN = "CASH_DISTRIBUTION_AVAILABILITY_UNKNOWN"
CASH_DISTRIBUTION_AVAILABLE_AFTER_EX = "CASH_DISTRIBUTION_AVAILABLE_AFTER_EX"

UNSUPPORTED_RELEVANT_STOCK_EVENT = "UNSUPPORTED_RELEVANT_STOCK_EVENT"
UNSUPPORTED_RELEVANT_SUBSCRIPTION = "UNSUPPORTED_RELEVANT_SUBSCRIPTION"
UNPARSED_RELEVANT_CASH_EVENT = "UNPARSED_RELEVANT_CASH_EVENT"
AMBIGUOUS_STOCK_EVENT_SCOPE = "AMBIGUOUS_STOCK_EVENT_SCOPE"
AMBIGUOUS_CASH_EVENT_SCOPE = "AMBIGUOUS_CASH_EVENT_SCOPE"
AMBIGUOUS_SUBSCRIPTION_SCOPE = "AMBIGUOUS_SUBSCRIPTION_SCOPE"
RELEVANT_EVENT_DATE_UNAVAILABLE = "RELEVANT_EVENT_DATE_UNAVAILABLE"
SAME_SESSION_SHARE_AND_CASH_ORDERING_UNVERIFIED = (
    "SAME_SESSION_SHARE_AND_CASH_ORDERING_UNVERIFIED"
)
B3_SUPPLEMENT_HISTORICAL_COMPLETENESS_UNPROVEN = (
    "B3_SUPPLEMENT_HISTORICAL_COMPLETENESS_UNPROVEN"
)

_TARGET = "TARGET"
_OTHER = "OTHER"
_AMBIGUOUS = "AMBIGUOUS"


@dataclass(frozen=True, slots=True)
class B3CashDistributionConversion:
    ticker: str
    kind: str
    amount_per_share: float
    event_asset_issued: str | None
    event_isin: str | None
    com_date: date
    ex_date: date | None
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
            "kind": self.kind,
            "amount_per_share": self.amount_per_share,
            "event_asset_issued": self.event_asset_issued,
            "event_isin": self.event_isin,
            "com_date": self.com_date.isoformat(),
            "ex_date": self.ex_date.isoformat() if self.ex_date is not None else None,
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


@dataclass(frozen=True, slots=True)
class B3EventAwareCoverageAudit:
    issuing_company: str
    ticker: str
    start_date: date
    end_date: date
    generated_at: datetime
    price_bar_count: int
    relevant_stock_event_count: int
    converted_share_action_count: int
    blocked_share_action_count: int
    relevant_cash_event_count: int
    parsed_relevant_cash_event_count: int
    converted_cash_distribution_count: int
    blocked_cash_distribution_count: int
    relevant_subscription_count: int
    converted_subscription_right_count: int
    blocked_subscription_right_count: int
    unsupported_event_count: int
    ambiguous_event_scope_count: int
    event_identity_mismatch_count: int
    share_conversions: tuple[B3ShareActionConversion, ...]
    cash_conversions: tuple[B3CashDistributionConversion, ...]
    subscription_conversions: tuple[B3SubscriptionRightConversion, ...]
    unsupported_stock_events: tuple[dict[str, Any], ...]
    unsupported_subscriptions: tuple[dict[str, Any], ...]
    unparsed_cash_events: tuple[dict[str, Any], ...]
    observed_blockers: tuple[str, ...]
    strict_blockers: tuple[str, ...]
    observed_event_coverage_complete: bool
    historical_source_completeness_proven: bool
    event_aware_return_path_ready: bool
    strict_event_aware_backtest_ready: bool
    readiness_promotion_allowed: bool = False
    price_adjustment_applied: bool = False
    price_series_blocker_removed: bool = False
    effect: str = "diagnostic_only_event_aware_coverage_no_readiness_change"
    schema_version: str = "0.2"

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "effect": self.effect,
            "issuing_company": self.issuing_company,
            "ticker": self.ticker,
            "start_date": self.start_date.isoformat(),
            "end_date": self.end_date.isoformat(),
            "generated_at": self.generated_at.isoformat(),
            "price_bar_count": self.price_bar_count,
            "relevant_stock_event_count": self.relevant_stock_event_count,
            "converted_share_action_count": self.converted_share_action_count,
            "blocked_share_action_count": self.blocked_share_action_count,
            "relevant_cash_event_count": self.relevant_cash_event_count,
            "parsed_relevant_cash_event_count": self.parsed_relevant_cash_event_count,
            "converted_cash_distribution_count": self.converted_cash_distribution_count,
            "blocked_cash_distribution_count": self.blocked_cash_distribution_count,
            "relevant_subscription_count": self.relevant_subscription_count,
            "subscription_count": self.relevant_subscription_count,
            "converted_subscription_right_count": self.converted_subscription_right_count,
            "blocked_subscription_right_count": self.blocked_subscription_right_count,
            "unsupported_event_count": self.unsupported_event_count,
            "ambiguous_event_scope_count": self.ambiguous_event_scope_count,
            "event_identity_mismatch_count": self.event_identity_mismatch_count,
            "share_conversions": [item.to_dict() for item in self.share_conversions],
            "cash_conversions": [item.to_dict() for item in self.cash_conversions],
            "subscription_conversions": [
                item.to_dict() for item in self.subscription_conversions
            ],
            "unsupported_stock_events": list(self.unsupported_stock_events),
            "unsupported_subscriptions": list(self.unsupported_subscriptions),
            "unparsed_cash_events": list(self.unparsed_cash_events),
            "observed_blockers": list(self.observed_blockers),
            "strict_blockers": list(self.strict_blockers),
            "observed_event_coverage_complete": self.observed_event_coverage_complete,
            "historical_source_completeness_proven": self.historical_source_completeness_proven,
            "event_aware_return_path_ready": self.event_aware_return_path_ready,
            "strict_event_aware_backtest_ready": self.strict_event_aware_backtest_ready,
            "readiness_promotion_allowed": self.readiness_promotion_allowed,
            "price_adjustment_applied": self.price_adjustment_applied,
            "price_series_blocker_removed": self.price_series_blocker_removed,
        }


def convert_b3_cash_distribution(
    *,
    ticker: str,
    payment: DividendPayment,
    bars: list[PriceBar],
) -> B3CashDistributionConversion:
    normalized_ticker = ticker.strip().upper()
    if not normalized_ticker:
        raise ValueError("ticker must not be blank")

    event_asset_issued = _optional_identity(payment.ticker)
    event_isin = _optional_identity(payment.isin)
    com_date = payment.ex_date
    kind = payment.kind.strip().upper()

    if kind not in {"DIVIDEND", "JCP"}:
        return _blocked_cash(
            ticker=normalized_ticker,
            payment=payment,
            status=CASH_DISTRIBUTION_KIND_UNSUPPORTED,
            blockers=(CASH_DISTRIBUTION_KIND_UNSUPPORTED,),
        )
    if payment.amount_per_share <= 0:
        return _blocked_cash(
            ticker=normalized_ticker,
            payment=payment,
            status=CASH_DISTRIBUTION_AMOUNT_INVALID,
            blockers=(CASH_DISTRIBUTION_AMOUNT_INVALID,),
        )

    if payment.date_basis != "LAST_DATE_PRIOR_TO_EX":
        return _blocked_cash(
            ticker=normalized_ticker,
            payment=payment,
            status=CASH_DISTRIBUTION_DATE_BASIS_UNSUPPORTED,
            blockers=(CASH_DISTRIBUTION_DATE_BASIS_UNSUPPORTED,),
        )
    ticker_bars = sorted(
        (bar for bar in bars if bar.ticker.upper() == normalized_ticker),
        key=lambda bar: bar.trade_date,
    )
    target_isins = {
        normalized
        for bar in ticker_bars
        for normalized in [_optional_identity(bar.isin)]
        if normalized is not None
    }
    asset_issued_isin = _asset_issued_isin(event_asset_issued, normalized_ticker)
    if (
        event_isin is not None
        and asset_issued_isin is not None
        and event_isin != asset_issued_isin
    ):
        return _blocked_cash(
            ticker=normalized_ticker,
            payment=payment,
            status=CASH_DISTRIBUTION_ISIN_MISMATCH,
            blockers=(CASH_DISTRIBUTION_ISIN_MISMATCH,),
        )
    identity_scope = _event_scope(
        asset_issued=event_asset_issued,
        isin=event_isin,
        ticker=normalized_ticker,
        target_isins=target_isins,
    )
    if identity_scope == _OTHER:
        return _blocked_cash(
            ticker=normalized_ticker,
            payment=payment,
            status=CASH_DISTRIBUTION_SCOPE_MISMATCH,
            blockers=(CASH_DISTRIBUTION_SCOPE_MISMATCH,),
        )
    if identity_scope == _AMBIGUOUS:
        return _blocked_cash(
            ticker=normalized_ticker,
            payment=payment,
            status=CASH_DISTRIBUTION_IDENTITY_INSUFFICIENT,
            blockers=(CASH_DISTRIBUTION_IDENTITY_INSUFFICIENT,),
        )

    com_bar = next((bar for bar in ticker_bars if bar.trade_date == com_date), None)
    if com_bar is None:
        return _blocked_cash(
            ticker=normalized_ticker,
            payment=payment,
            status=CASH_DISTRIBUTION_COM_BAR_MISSING,
            blockers=(CASH_DISTRIBUTION_COM_BAR_MISSING,),
        )
    ex_bar = next((bar for bar in ticker_bars if bar.trade_date > com_date), None)
    if ex_bar is None:
        return _blocked_cash(
            ticker=normalized_ticker,
            payment=payment,
            status=CASH_DISTRIBUTION_EX_BAR_MISSING,
            blockers=(CASH_DISTRIBUTION_EX_BAR_MISSING,),
        )

    bar_isins = {
        normalized
        for bar in (com_bar, ex_bar)
        for normalized in [_optional_identity(bar.isin)]
        if normalized is not None
    }
    asserted_isins = {
        value
        for value in (event_isin, asset_issued_isin)
        if value is not None
    }
    if len(asserted_isins) > 1:
        return _blocked_cash(
            ticker=normalized_ticker,
            payment=payment,
            status=CASH_DISTRIBUTION_ISIN_MISMATCH,
            blockers=(CASH_DISTRIBUTION_ISIN_MISMATCH,),
            ex_date=ex_bar.trade_date,
        )
    asserted_isin = next(iter(asserted_isins), None)
    if asserted_isin is not None and not bar_isins:
        return _blocked_cash(
            ticker=normalized_ticker,
            payment=payment,
            status=CASH_DISTRIBUTION_IDENTITY_INSUFFICIENT,
            blockers=(CASH_DISTRIBUTION_IDENTITY_INSUFFICIENT,),
            ex_date=ex_bar.trade_date,
        )
    if asserted_isin is not None and bar_isins != {asserted_isin}:
        return _blocked_cash(
            ticker=normalized_ticker,
            payment=payment,
            status=CASH_DISTRIBUTION_ISIN_MISMATCH,
            blockers=(CASH_DISTRIBUTION_ISIN_MISMATCH,),
            ex_date=ex_bar.trade_date,
        )

    available_from = (
        _aware(payment.available_from) if payment.available_from is not None else None
    )
    if available_from is None:
        return _blocked_cash(
            ticker=normalized_ticker,
            payment=payment,
            status=CASH_DISTRIBUTION_AVAILABILITY_UNKNOWN,
            blockers=(CASH_DISTRIBUTION_AVAILABILITY_UNKNOWN,),
            ex_date=ex_bar.trade_date,
        )
    if available_from.date() > ex_bar.trade_date:
        return _blocked_cash(
            ticker=normalized_ticker,
            payment=payment,
            status=CASH_DISTRIBUTION_AVAILABLE_AFTER_EX,
            blockers=(CASH_DISTRIBUTION_AVAILABLE_AFTER_EX,),
            ex_date=ex_bar.trade_date,
        )

    distribution = CashDistribution(
        ticker=normalized_ticker,
        ex_date=ex_bar.trade_date,
        amount_per_share=payment.amount_per_share,
    )
    return B3CashDistributionConversion(
        ticker=normalized_ticker,
        kind=kind,
        amount_per_share=payment.amount_per_share,
        event_asset_issued=event_asset_issued,
        event_isin=event_isin,
        com_date=com_date,
        ex_date=ex_bar.trade_date,
        available_from=available_from,
        point_in_time_eligible=True,
        status=CASH_DISTRIBUTION_CONVERTED,
        blockers=(),
        distribution=distribution,
    )


def audit_b3_event_aware_coverage(
    *,
    issuing_company: str,
    ticker: str,
    payload: dict[str, Any],
    bars: list[PriceBar],
    start_date: date,
    end_date: date,
    generated_at: datetime | None = None,
) -> B3EventAwareCoverageAudit:
    if end_date < start_date:
        raise ValueError("end_date must not be before start_date")

    normalized_ticker = ticker.strip().upper()
    normalized_company = _optional_identity(issuing_company)
    if normalized_company is None:
        raise ValueError("issuing_company must not be blank")

    generated = _aware(generated_at or datetime.now(UTC))
    contract = B3CorporateActionsContractAuditor.audit_payload(
        normalized_company,
        payload,
        source_url="B3_PUBLIC_LISTED_COMPANIES",
    )
    payments = B3DividendCollector.parse_cash_dividends(
        payload,
        collected_at=generated,
        source_url="B3_PUBLIC_LISTED_COMPANIES",
    )
    target_isins = {
        normalized
        for bar in bars
        if bar.ticker.upper() == normalized_ticker
        for normalized in [_optional_identity(bar.isin)]
        if normalized is not None
    }

    observed_blockers: set[str] = set()
    ambiguous_scope_count = 0

    relevant_stock: list[B3StockActionContractRecord] = []
    unsupported_stock: list[dict[str, Any]] = []
    for stock_event in contract.stock_actions:
        if stock_event.last_date_prior is not None and not _event_in_window(
            stock_event.last_date_prior,
            start_date,
            end_date,
        ):
            continue
        scope = _event_scope(
            asset_issued=stock_event.asset_issued,
            isin=stock_event.isin_code,
            ticker=normalized_ticker,
            target_isins=target_isins,
        )
        if scope == _AMBIGUOUS:
            ambiguous_scope_count += 1
            observed_blockers.add(AMBIGUOUS_STOCK_EVENT_SCOPE)
            continue
        if scope == _OTHER:
            continue
        if stock_event.last_date_prior is None:
            observed_blockers.add(RELEVANT_EVENT_DATE_UNAVAILABLE)
        relevant_stock.append(stock_event)
        if not stock_event.supported_label:
            observed_blockers.add(UNSUPPORTED_RELEVANT_STOCK_EVENT)
            unsupported_stock.append(stock_event.to_dict())

    share_conversions: list[B3ShareActionConversion] = []
    for stock_event in relevant_stock:
        if not stock_event.supported_label:
            continue
        share_conversion = convert_b3_stock_action(
            issuing_company=normalized_company,
            ticker=normalized_ticker,
            event=stock_event,
            bars=bars,
        )
        share_conversions.append(share_conversion)
        observed_blockers.update(share_conversion.blockers)

    relevant_payments: list[DividendPayment] = []
    for payment in payments:
        if not _event_in_window(payment.ex_date, start_date, end_date):
            continue
        scope = _event_scope(
            asset_issued=payment.ticker,
            isin=payment.isin,
            ticker=normalized_ticker,
            target_isins=target_isins,
        )
        if scope == _AMBIGUOUS:
            continue
        if scope == _OTHER:
            continue
        relevant_payments.append(payment)

    raw_relevant_cash, unparsed_cash, raw_cash_ambiguous = _raw_cash_coverage(
        payload=payload,
        ticker=normalized_ticker,
        target_isins=target_isins,
        start_date=start_date,
        end_date=end_date,
        parsed_relevant_count=len(relevant_payments),
    )
    ambiguous_scope_count += raw_cash_ambiguous
    if raw_cash_ambiguous:
        observed_blockers.add(AMBIGUOUS_CASH_EVENT_SCOPE)
    if unparsed_cash:
        observed_blockers.add(UNPARSED_RELEVANT_CASH_EVENT)

    cash_conversions = [
        convert_b3_cash_distribution(
            ticker=normalized_ticker,
            payment=payment,
            bars=bars,
        )
        for payment in relevant_payments
    ]
    for cash_conversion in cash_conversions:
        observed_blockers.update(cash_conversion.blockers)

    relevant_subscriptions: list[B3SubscriptionContractRecord] = []
    for subscription_event in contract.subscriptions:
        if (
            subscription_event.last_date_prior is not None
            and not _event_in_window(
                subscription_event.last_date_prior,
                start_date,
                end_date,
            )
        ):
            continue
        scope = _event_scope(
            asset_issued=subscription_event.asset_issued,
            isin=subscription_event.isin_code,
            ticker=normalized_ticker,
            target_isins=target_isins,
        )
        if scope == _AMBIGUOUS:
            ambiguous_scope_count += 1
            observed_blockers.add(AMBIGUOUS_SUBSCRIPTION_SCOPE)
            continue
        if scope == _OTHER:
            continue
        if subscription_event.last_date_prior is None:
            observed_blockers.add(RELEVANT_EVENT_DATE_UNAVAILABLE)
        relevant_subscriptions.append(subscription_event)

    subscription_conversions: list[B3SubscriptionRightConversion] = []
    unsupported_subscriptions: list[dict[str, Any]] = []
    for subscription_event in relevant_subscriptions:
        subscription_conversion = convert_b3_subscription_right(
            ticker=normalized_ticker,
            event=subscription_event,
            bars=bars,
        )
        subscription_conversions.append(subscription_conversion)
        observed_blockers.update(subscription_conversion.blockers)
        if not subscription_conversion.converted:
            unsupported_subscriptions.append(subscription_event.to_dict())
            observed_blockers.add(UNSUPPORTED_RELEVANT_SUBSCRIPTION)

    share_dates = {
        item.action.ex_date
        for item in share_conversions
        if item.action is not None
    }
    distribution_dates = {
        item.distribution.ex_date
        for item in cash_conversions
        if item.distribution is not None
    } | {
        item.distribution.ex_date
        for item in subscription_conversions
        if item.distribution is not None
    }
    if share_dates & distribution_dates:
        observed_blockers.add(SAME_SESSION_SHARE_AND_CASH_ORDERING_UNVERIFIED)

    converted_share = sum(item.converted for item in share_conversions)
    converted_cash = sum(item.converted for item in cash_conversions)
    converted_subscription = sum(item.converted for item in subscription_conversions)
    blocked_share = len(relevant_stock) - len(unsupported_stock) - converted_share
    blocked_cash = len(relevant_payments) - converted_cash
    blocked_subscription = len(relevant_subscriptions) - converted_subscription

    observed = tuple(sorted(observed_blockers))
    strict = tuple(
        sorted(
            observed_blockers
            | {B3_SUPPLEMENT_HISTORICAL_COMPLETENESS_UNPROVEN}
        )
    )
    observed_complete = not observed
    identity_blockers = {
        CASH_DISTRIBUTION_SCOPE_MISMATCH,
        CASH_DISTRIBUTION_ISIN_MISMATCH,
        CASH_DISTRIBUTION_IDENTITY_INSUFFICIENT,
        SUBSCRIPTION_RIGHT_IDENTITY_INSUFFICIENT,
        SUBSCRIPTION_RIGHT_ISIN_MISMATCH,
        AMBIGUOUS_STOCK_EVENT_SCOPE,
        AMBIGUOUS_CASH_EVENT_SCOPE,
        AMBIGUOUS_SUBSCRIPTION_SCOPE,
    }
    identity_mismatches = (
        ambiguous_scope_count
        + sum(
            bool(set(item.blockers) & identity_blockers)
            for item in cash_conversions
        )
        + sum(
            bool(set(item.blockers) & identity_blockers)
            for item in subscription_conversions
        )
        + sum(
            any("ISIN_MISMATCH" in blocker for blocker in item.blockers)
            for item in share_conversions
        )
    )
    price_bar_count = sum(
        bar.ticker.upper() == normalized_ticker
        and start_date <= bar.trade_date <= end_date
        for bar in bars
    )

    return B3EventAwareCoverageAudit(
        issuing_company=normalized_company,
        ticker=normalized_ticker,
        start_date=start_date,
        end_date=end_date,
        generated_at=generated,
        price_bar_count=price_bar_count,
        relevant_stock_event_count=len(relevant_stock),
        converted_share_action_count=converted_share,
        blocked_share_action_count=blocked_share + len(unsupported_stock),
        relevant_cash_event_count=raw_relevant_cash,
        parsed_relevant_cash_event_count=len(relevant_payments),
        converted_cash_distribution_count=converted_cash,
        blocked_cash_distribution_count=blocked_cash + len(unparsed_cash),
        relevant_subscription_count=len(relevant_subscriptions),
        converted_subscription_right_count=converted_subscription,
        blocked_subscription_right_count=blocked_subscription,
        unsupported_event_count=(
            len(unsupported_stock) + len(unsupported_subscriptions) + len(unparsed_cash)
        ),
        ambiguous_event_scope_count=ambiguous_scope_count,
        event_identity_mismatch_count=identity_mismatches,
        share_conversions=tuple(share_conversions),
        cash_conversions=tuple(cash_conversions),
        subscription_conversions=tuple(subscription_conversions),
        unsupported_stock_events=tuple(unsupported_stock),
        unsupported_subscriptions=tuple(unsupported_subscriptions),
        unparsed_cash_events=tuple(unparsed_cash),
        observed_blockers=observed,
        strict_blockers=strict,
        observed_event_coverage_complete=observed_complete,
        historical_source_completeness_proven=False,
        event_aware_return_path_ready=False,
        strict_event_aware_backtest_ready=False,
    )


def _raw_cash_coverage(
    *,
    payload: dict[str, Any],
    ticker: str,
    target_isins: set[str],
    start_date: date,
    end_date: date,
    parsed_relevant_count: int,
) -> tuple[int, list[dict[str, Any]], int]:
    raw = payload.get("cashDividends") or []
    if not isinstance(raw, list):
        raise TypeError("B3 cashDividends must be a list")

    relevant: list[dict[str, Any]] = []
    unparsed: list[dict[str, Any]] = []
    ambiguous = 0
    for item in raw:
        if not isinstance(item, dict):
            continue
        scope = _event_scope(
            asset_issued=_text(item.get("assetIssued")),
            isin=_text(item.get("isinCode")),
            ticker=ticker,
            target_isins=target_isins,
        )
        event_date = _parse_date(item.get("lastDatePrior"))
        if scope == _AMBIGUOUS:
            if event_date is None or _event_in_window(event_date, start_date, end_date):
                ambiguous += 1
            continue
        if scope == _OTHER:
            continue
        if event_date is not None and not _event_in_window(
            event_date,
            start_date,
            end_date,
        ):
            continue
        summary = _raw_cash_summary(item)
        relevant.append(summary)
        if not _raw_cash_is_parsable(item):
            unparsed.append(summary)

    if len(relevant) - len(unparsed) != parsed_relevant_count:
        raise ValueError(
            "raw/parsed relevant cash event accounting mismatch: "
            f"raw={len(relevant)} unparsed={len(unparsed)} parsed={parsed_relevant_count}"
        )
    return len(relevant), unparsed, ambiguous


def _raw_cash_is_parsable(item: dict[str, Any]) -> bool:
    event_date = _parse_date(item.get("lastDatePrior"))
    rate = _parse_number(item.get("rate"))
    label = str(item.get("label") or "").upper()
    supported_kind = (
        "JCP" in label
        or "CAP" in label
        or "JURO" in label
        or "DIVID" in label
    )
    return event_date is not None and rate is not None and rate > 0 and supported_kind


def _event_scope(
    *,
    asset_issued: str | None,
    isin: str | None,
    ticker: str,
    target_isins: set[str],
) -> str:
    normalized_asset = _optional_identity(asset_issued)
    normalized_isin = _optional_identity(isin)
    relations: list[str] = []

    if normalized_asset is not None:
        if normalized_asset == ticker or normalized_asset in target_isins:
            relations.append(_TARGET)
        elif _looks_like_isin(normalized_asset) and not target_isins:
            relations.append(_AMBIGUOUS)
        else:
            relations.append(_OTHER)

    if normalized_isin is not None:
        if normalized_isin in target_isins:
            relations.append(_TARGET)
        elif target_isins:
            relations.append(_OTHER)
        else:
            relations.append(_AMBIGUOUS)

    if not relations or _AMBIGUOUS in relations:
        return _AMBIGUOUS
    if _TARGET in relations and _OTHER in relations:
        return _AMBIGUOUS
    return _TARGET if _TARGET in relations else _OTHER


def _event_in_window(value: date | None, start_date: date, end_date: date) -> bool:
    return value is not None and start_date <= value <= end_date


def _blocked_cash(
    *,
    ticker: str,
    payment: DividendPayment,
    status: str,
    blockers: tuple[str, ...],
    ex_date: date | None = None,
) -> B3CashDistributionConversion:
    return B3CashDistributionConversion(
        ticker=ticker,
        kind=payment.kind.upper(),
        amount_per_share=payment.amount_per_share,
        event_asset_issued=_optional_identity(payment.ticker),
        event_isin=_optional_identity(payment.isin),
        com_date=payment.ex_date,
        ex_date=ex_date,
        available_from=(
            _aware(payment.available_from) if payment.available_from is not None else None
        ),
        point_in_time_eligible=False,
        status=status,
        blockers=tuple(sorted(set(blockers))),
        distribution=None,
    )


def _raw_cash_summary(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "asset_issued": _text(item.get("assetIssued")),
        "label": _text(item.get("label")),
        "rate": item.get("rate"),
        "last_date_prior": _text(item.get("lastDatePrior")),
        "isin_code": _text(item.get("isinCode")),
    }


def _parse_date(value: Any) -> date | None:
    text = _text(value)
    if text is None:
        return None
    try:
        return date.fromisoformat(text)
    except ValueError:
        pass
    if "T" in text:
        try:
            return date.fromisoformat(text.split("T", 1)[0])
        except ValueError:
            pass
    parts = text.split("/")
    if len(parts) == 3:
        try:
            day, month, year = (int(part) for part in parts)
            return date(year, month, day)
        except ValueError:
            pass
    return None


def _parse_number(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace(" ", "")
    if not text:
        return None
    if "," in text:
        text = text.replace(".", "").replace(",", ".")
    try:
        return float(text)
    except ValueError:
        return None


def _optional_identity(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = "".join(character for character in str(value).upper() if character.isalnum())
    return normalized or None


def _asset_issued_isin(asset_issued: str | None, ticker: str) -> str | None:
    normalized = _optional_identity(asset_issued)
    if normalized is None or normalized == ticker:
        return None
    return normalized if _looks_like_isin(normalized) else None


def _looks_like_isin(value: str) -> bool:
    return len(value) == 12 and value[:2].isalpha() and value.isalnum()


def _text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
