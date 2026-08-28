from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from typing import Any

import httpx

from ultimate_stock_analyzer.dividends.regularity import DividendPayment

B3_SUPPLEMENT_URL = (
    "https://sistemaswebb3-listados.b3.com.br/"
    "listedCompaniesProxy/CompanyCall/GetListedSupplementCompany"
)


@dataclass(slots=True)
class B3DividendCollector:
    user_agent: str = "ultimate-stock-analyzer/0.4"
    timeout_seconds: float = 30.0
    language: str = "pt-br"

    def build_url(self, issuing_company: str) -> str:
        code = "".join(character for character in issuing_company.upper() if character.isalnum())
        if not code:
            raise ValueError("invalid issuing company code")
        payload = json.dumps({"issuingCompany": code, "language": self.language})
        encoded = base64.b64encode(payload.encode("utf-8")).decode("ascii")
        return f"{B3_SUPPLEMENT_URL}/{encoded}"

    def fetch_payload(self, issuing_company: str) -> dict[str, Any]:
        with httpx.Client(timeout=self.timeout_seconds, follow_redirects=True) as client:
            response = client.get(
                self.build_url(issuing_company),
                headers={"User-Agent": self.user_agent},
            )
            response.raise_for_status()
            payload = response.json()
        if not isinstance(payload, dict):
            raise TypeError("unexpected B3 corporate-actions response")
        return payload

    def fetch(self, issuing_company: str, *, collected_at: datetime) -> list[DividendPayment]:
        payload = self.fetch_payload(issuing_company)
        return self.parse_cash_dividends(
            payload,
            collected_at=collected_at,
            source_url=self.build_url(issuing_company),
        )

    @staticmethod
    def parse_cash_dividends(
        payload: dict[str, Any],
        *,
        collected_at: datetime,
        source_url: str | None = None,
    ) -> list[DividendPayment]:
        raw_events = payload.get("cashDividends") or []
        if not isinstance(raw_events, list):
            raise TypeError("B3 cashDividends must be a list")

        payments: list[DividendPayment] = []
        for event in raw_events:
            if not isinstance(event, dict):
                continue
            last_date_prior = _parse_date(event.get("lastDatePrior"))
            rate = _parse_number(event.get("rate"))
            if last_date_prior is None or rate is None or rate <= 0:
                continue
            label = str(event.get("label") or "").strip()
            remarks = _optional_text(event.get("remarks"))
            kind = _normalize_kind(label)
            if kind not in {"DIVIDEND", "JCP"}:
                continue
            approved_on = _parse_date(event.get("approvedOn"))
            available_from = _conservative_availability(approved_on)
            text_for_classification = f"{label} {remarks or ''}".upper()
            extraordinary = "EXTRAORD" in text_for_classification

            payments.append(
                DividendPayment(
                    ex_date=last_date_prior,
                    amount_per_share=rate,
                    kind=kind,
                    extraordinary=extraordinary,
                    ticker=_optional_text(event.get("assetIssued")),
                    isin=_optional_text(event.get("isinCode")),
                    declared_date=approved_on,
                    payment_date=_parse_date(event.get("paymentDate")),
                    available_from=available_from,
                    collected_at=_aware(collected_at),
                    source="B3_PUBLIC_LISTED_COMPANIES",
                    source_url=source_url,
                    related_to=_optional_text(event.get("relatedTo")),
                    remarks=remarks,
                    date_basis="LAST_DATE_PRIOR_TO_EX",
                )
            )
        return sorted(payments, key=lambda payment: payment.ex_date)


def _normalize_kind(label: str) -> str:
    normalized = label.upper()
    if "JCP" in normalized or "CAP" in normalized or "JURO" in normalized:
        return "JCP"
    if "DIVID" in normalized:
        return "DIVIDEND"
    return "OTHER"


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
    try:
        return datetime.strptime(text_value, "%d/%m/%Y").replace(tzinfo=UTC).date()
    except ValueError:
        return None


def _conservative_availability(approved_on: date | None) -> datetime | None:
    if approved_on is None:
        return None
    next_day = approved_on + timedelta(days=1)
    return datetime.combine(next_day, time.min, tzinfo=UTC)


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text_value = str(value).strip()
    return text_value or None


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
