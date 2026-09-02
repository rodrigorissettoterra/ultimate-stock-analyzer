from __future__ import annotations

import re
import unicodedata
from dataclasses import asdict, dataclass
from datetime import date, datetime
from typing import Any

from ultimate_stock_analyzer.collectors.b3_dividends import B3DividendCollector

SUPPORTED_SHARE_ACTION_LABELS = frozenset(
    {
        "BONIFICACAO",
        "DESDOBRAMENTO",
        "GRUPAMENTO",
    }
)

READY_COMPLETE_FACTOR = "READY_COMPLETE_FACTOR"
SUPPORTED_LABEL_MISSING_COMPLETE_FACTOR = "SUPPORTED_LABEL_MISSING_COMPLETE_FACTOR"
SUPPORTED_LABEL_INVALID_COMPLETE_FACTOR = "SUPPORTED_LABEL_INVALID_COMPLETE_FACTOR"
SUPPORTED_LABEL_FACTOR_CONFLICT = "SUPPORTED_LABEL_FACTOR_CONFLICT"
SUPPORTED_LABEL_MISSING_EX_DATE = "SUPPORTED_LABEL_MISSING_EX_DATE"
UNSUPPORTED_STOCK_EVENT_LABEL = "UNSUPPORTED_STOCK_EVENT_LABEL"
UNSUPPORTED_SUBSCRIPTION_RIGHTS = "UNSUPPORTED_SUBSCRIPTION_RIGHTS"

_COMPLETE_FACTOR_PATTERN = re.compile(
    r"^\s*(\d+(?:[.,]\d+)?)\s*(?:PARA|:|/)\s*(\d+(?:[.,]\d+)?)\s*$",
    flags=re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class B3StockActionContractRecord:
    asset_issued: str | None
    label: str
    normalized_label: str
    factor: float | None
    complete_factor: str | None
    approved_on: date | None
    last_date_prior: date | None
    isin_code: str | None
    remarks: str | None
    supported_label: bool
    ratio_new_per_old: float | None
    factor_matches_complete_factor: bool | None
    conversion_status: str

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        for key in ("approved_on", "last_date_prior"):
            value = payload[key]
            payload[key] = value.isoformat() if value is not None else None
        return payload


@dataclass(frozen=True, slots=True)
class B3SubscriptionContractRecord:
    asset_issued: str | None
    label: str
    percentage: float | None
    price_unit: float | None
    approved_on: date | None
    last_date_prior: date | None
    subscription_date: date | None
    trading_period: str | None
    isin_code: str | None
    remarks: str | None
    status: str = UNSUPPORTED_SUBSCRIPTION_RIGHTS

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        for key in ("approved_on", "last_date_prior", "subscription_date"):
            value = payload[key]
            payload[key] = value.isoformat() if value is not None else None
        return payload


@dataclass(frozen=True, slots=True)
class B3CorporateActionsContractAudit:
    issuing_company: str
    source_url: str
    payload_keys: tuple[str, ...]
    stock_actions: tuple[B3StockActionContractRecord, ...]
    subscriptions: tuple[B3SubscriptionContractRecord, ...]
    blockers: tuple[str, ...]

    @property
    def observed_stock_labels(self) -> tuple[str, ...]:
        return tuple(sorted({record.normalized_label for record in self.stock_actions}))

    @property
    def conversion_ready_stock_actions(self) -> int:
        return sum(
            record.conversion_status == READY_COMPLETE_FACTOR for record in self.stock_actions
        )

    @property
    def ambiguous_stock_actions(self) -> int:
        return sum(
            record.supported_label and record.conversion_status != READY_COMPLETE_FACTOR
            for record in self.stock_actions
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "issuing_company": self.issuing_company,
            "source_url": self.source_url,
            "payload_keys": list(self.payload_keys),
            "stock_action_count": len(self.stock_actions),
            "subscription_count": len(self.subscriptions),
            "supported_stock_action_count": sum(
                record.supported_label for record in self.stock_actions
            ),
            "conversion_ready_stock_action_count": self.conversion_ready_stock_actions,
            "ambiguous_stock_action_count": self.ambiguous_stock_actions,
            "observed_stock_labels": list(self.observed_stock_labels),
            "stock_actions": [record.to_dict() for record in self.stock_actions],
            "subscriptions": [record.to_dict() for record in self.subscriptions],
            "blockers": list(self.blockers),
        }


@dataclass(slots=True)
class B3CorporateActionsContractAuditor:
    collector: B3DividendCollector

    @classmethod
    def default(cls) -> B3CorporateActionsContractAuditor:
        return cls(collector=B3DividendCollector())

    def audit(self, issuing_company: str) -> B3CorporateActionsContractAudit:
        payload = self.collector.fetch_payload(issuing_company)
        return self.audit_payload(
            issuing_company,
            payload,
            source_url=self.collector.build_url(issuing_company),
        )

    @staticmethod
    def audit_payload(
        issuing_company: str,
        payload: dict[str, Any],
        *,
        source_url: str,
    ) -> B3CorporateActionsContractAudit:
        stock_actions = tuple(_parse_stock_actions(payload))
        subscriptions = tuple(_parse_subscriptions(payload))
        blockers: set[str] = set()

        for record in stock_actions:
            if record.conversion_status != READY_COMPLETE_FACTOR:
                blockers.add(record.conversion_status)
        if subscriptions:
            blockers.add(UNSUPPORTED_SUBSCRIPTION_RIGHTS)

        return B3CorporateActionsContractAudit(
            issuing_company=_normalize_company_code(issuing_company),
            source_url=source_url,
            payload_keys=tuple(sorted(payload)),
            stock_actions=stock_actions,
            subscriptions=subscriptions,
            blockers=tuple(sorted(blockers)),
        )


def _parse_stock_actions(payload: dict[str, Any]) -> list[B3StockActionContractRecord]:
    raw_events = payload.get("stockDividends")
    if raw_events is None:
        raw_events = []
    if not isinstance(raw_events, list):
        raise TypeError("B3 stockDividends must be a list")

    records: list[B3StockActionContractRecord] = []
    for event in raw_events:
        if not isinstance(event, dict):
            continue
        label = str(event.get("label") or "").strip()
        normalized_label = _normalize_label(label)
        factor = _parse_number(event.get("factor"))
        complete_factor = _optional_text(event.get("completeFactor"))
        ratio = _parse_complete_factor(complete_factor)
        last_date_prior = _parse_date(event.get("lastDatePrior"))
        supported = normalized_label in SUPPORTED_SHARE_ACTION_LABELS
        factor_matches: bool | None = None

        if not supported:
            status = UNSUPPORTED_STOCK_EVENT_LABEL
            ratio = None
        elif last_date_prior is None:
            status = SUPPORTED_LABEL_MISSING_EX_DATE
            ratio = None
        elif complete_factor is None:
            status = SUPPORTED_LABEL_MISSING_COMPLETE_FACTOR
        elif ratio is None:
            status = SUPPORTED_LABEL_INVALID_COMPLETE_FACTOR
        else:
            if factor is not None:
                factor_matches = abs(factor - ratio) <= 1e-9
            if factor_matches is False:
                status = SUPPORTED_LABEL_FACTOR_CONFLICT
                ratio = None
            else:
                status = READY_COMPLETE_FACTOR

        records.append(
            B3StockActionContractRecord(
                asset_issued=_optional_text(event.get("assetIssued")),
                label=label,
                normalized_label=normalized_label,
                factor=factor,
                complete_factor=complete_factor,
                approved_on=_parse_date(event.get("approvedOn")),
                last_date_prior=last_date_prior,
                isin_code=_optional_text(event.get("isinCode")),
                remarks=_optional_text(event.get("remarks")),
                supported_label=supported,
                ratio_new_per_old=ratio,
                factor_matches_complete_factor=factor_matches,
                conversion_status=status,
            )
        )
    return records


def _parse_subscriptions(payload: dict[str, Any]) -> list[B3SubscriptionContractRecord]:
    raw_events = payload.get("subscriptions")
    if raw_events is None:
        raw_events = []
    if not isinstance(raw_events, list):
        raise TypeError("B3 subscriptions must be a list")

    records: list[B3SubscriptionContractRecord] = []
    for event in raw_events:
        if not isinstance(event, dict):
            continue
        records.append(
            B3SubscriptionContractRecord(
                asset_issued=_optional_text(event.get("assetIssued")),
                label=str(event.get("label") or "").strip(),
                percentage=_parse_number(event.get("percentage")),
                price_unit=_parse_number(event.get("priceUnit")),
                approved_on=_parse_date(event.get("approvedOn")),
                last_date_prior=_parse_date(event.get("lastDatePrior")),
                subscription_date=_parse_date(event.get("subscriptionDate")),
                trading_period=_optional_text(event.get("tradingPeriod")),
                isin_code=_optional_text(event.get("isinCode")),
                remarks=_optional_text(event.get("remarks")),
            )
        )
    return records


def _parse_complete_factor(value: str | None) -> float | None:
    if value is None:
        return None
    match = _COMPLETE_FACTOR_PATTERN.match(value)
    if match is None:
        return None
    numerator = _parse_number(match.group(1))
    denominator = _parse_number(match.group(2))
    if numerator is None or denominator is None or numerator <= 0 or denominator <= 0:
        return None
    return numerator / denominator


def _normalize_label(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value)
    ascii_value = "".join(
        character for character in decomposed if not unicodedata.combining(character)
    )
    return re.sub(r"[^A-Z0-9]+", "_", ascii_value.upper()).strip("_")


def _normalize_company_code(value: str) -> str:
    code = "".join(character for character in value.upper() if character.isalnum())
    if not code:
        raise ValueError("invalid issuing company code")
    return code


def _parse_number(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text_value = str(value).strip().replace(" ", "")
    if not text_value:
        return None
    if "," in text_value:
        text_value = text_value.replace(".", "").replace(",", ".")
    try:
        return float(text_value)
    except ValueError:
        return None


def _parse_date(value: Any) -> date | None:
    if value is None:
        return None
    text_value = str(value).strip()
    if not text_value:
        return None
    try:
        return date.fromisoformat(text_value)
    except ValueError:
        pass
    for date_format in ("%d/%m/%Y", "%Y-%m-%dT%H:%M:%S.%fZ"):
        try:
            return datetime.strptime(text_value, date_format).date()
        except ValueError:
            continue
    return None


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text_value = str(value).strip()
    return text_value or None
