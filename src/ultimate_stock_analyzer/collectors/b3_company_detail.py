from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

import httpx

B3_LISTED_COMPANIES_PAGE = (
    "https://sistemaswebb3-listados.b3.com.br/"
    "listedCompaniesPage/?language=pt-br"
)
B3_COMPANY_API_BASE = (
    "https://sistemaswebb3-listados.b3.com.br/"
    "listedCompaniesProxy/CompanyCall"
)


@dataclass(frozen=True, slots=True)
class B3ListedSecurityCode:
    code: str
    isin: str | None


@dataclass(frozen=True, slots=True)
class B3ListedCompanyDetail:
    company_id: str
    cvm_code: int
    cnpj: str | None
    company_name: str | None
    trading_name: str | None
    issuer_code: str | None
    primary_code: str | None
    security_codes: tuple[B3ListedSecurityCode, ...]
    share_quotation_start: date | None
    has_quotation: str | None
    has_bdr: bool | None
    bdr_type: str | None
    market: str | None
    market_indicator: str | None
    status: str | None
    activity: str | None
    industry_classification: str | None
    collected_at: datetime
    source: str = "B3_LISTED_COMPANIES_GET_DETAIL"

    @property
    def all_security_codes(self) -> tuple[str, ...]:
        values: list[str] = []
        if self.primary_code:
            values.append(self.primary_code)
        values.extend(item.code for item in self.security_codes)
        return tuple(dict.fromkeys(values))


@dataclass(slots=True)
class B3ListedCompanyDetailCollector:
    timeout_seconds: float = 60.0
    user_agent: str = "ultimate-stock-analyzer/0.2"
    max_attempts: int = 3

    def detail_url(self, cvm_code: int) -> str:
        if cvm_code <= 0:
            raise ValueError("cvm_code must be positive")
        payload = json.dumps(
            {"codeCVM": str(cvm_code), "language": "pt-br"},
            separators=(",", ":"),
            ensure_ascii=True,
        ).encode()
        token = base64.b64encode(payload).decode()
        return f"{B3_COMPANY_API_BASE}/GetDetail/{token}"

    def fetch(self, cvm_code: int, *, collected_at: datetime) -> B3ListedCompanyDetail:
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")
        headers = {
            "Accept": "application/json, text/plain, */*",
            "User-Agent": self.user_agent,
            "Referer": B3_LISTED_COMPANIES_PAGE,
        }
        url = self.detail_url(cvm_code)
        with httpx.Client(
            timeout=self.timeout_seconds,
            follow_redirects=True,
            headers=headers,
        ) as client:
            for attempt in range(1, self.max_attempts + 1):
                try:
                    response = client.get(url)
                except httpx.TransportError:
                    if attempt == self.max_attempts:
                        raise
                    continue
                retryable = response.status_code == 429 or response.status_code >= 500
                if retryable and attempt < self.max_attempts:
                    continue
                response.raise_for_status()
                body = response.json()
                return self.parse(body, expected_cvm_code=cvm_code, collected_at=collected_at)
        raise RuntimeError("B3 GetDetail download exhausted without a response")

    def parse(
        self,
        payload: Any,
        *,
        expected_cvm_code: int,
        collected_at: datetime,
    ) -> B3ListedCompanyDetail:
        if not isinstance(payload, dict):
            raise TypeError("B3 GetDetail response must be an object")
        returned_cvm = _positive_int(payload.get("codeCVM"), "codeCVM")
        if returned_cvm != expected_cvm_code:
            raise ValueError(
                "B3 GetDetail returned unexpected CVM code: "
                f"expected={expected_cvm_code} actual={returned_cvm}"
            )

        raw_other_codes = payload.get("otherCodes")
        if raw_other_codes is None:
            raw_other_codes = []
        if not isinstance(raw_other_codes, list):
            raise TypeError("B3 GetDetail otherCodes must be a list")
        security_codes: list[B3ListedSecurityCode] = []
        for item in raw_other_codes:
            if not isinstance(item, dict):
                raise TypeError("B3 GetDetail otherCodes item must be an object")
            code = _text(item.get("code"))
            if code is None:
                continue
            security_codes.append(
                B3ListedSecurityCode(
                    code=code.upper(),
                    isin=_text(item.get("isin")),
                )
            )

        return B3ListedCompanyDetail(
            company_id=f"cvm:{returned_cvm}",
            cvm_code=returned_cvm,
            cnpj=_digits(payload.get("cnpj")),
            company_name=_text(payload.get("companyName")),
            trading_name=_text(payload.get("tradingName")),
            issuer_code=_upper(payload.get("issuingCompany")),
            primary_code=_upper(payload.get("code")),
            security_codes=tuple(security_codes),
            share_quotation_start=_date_br(payload.get("dateQuotation")),
            has_quotation=_upper(payload.get("hasQuotation")),
            has_bdr=_optional_bool(payload.get("hasBDR")),
            bdr_type=_text(payload.get("typeBDR")),
            market=_text(payload.get("market")),
            market_indicator=_text(payload.get("marketIndicator")),
            status=_text(payload.get("status")),
            activity=_text(payload.get("activity")),
            industry_classification=_text(payload.get("industryClassification")),
            collected_at=collected_at,
        )


def _text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _upper(value: object) -> str | None:
    text = _text(value)
    return text.upper() if text else None


def _digits(value: object) -> str | None:
    text = _text(value)
    if text is None:
        return None
    digits = "".join(character for character in text if character.isdigit())
    return digits or None


def _positive_int(value: object, field_name: str) -> int:
    text = _text(value)
    if text is None or not text.isdigit():
        raise ValueError(f"B3 GetDetail {field_name} must be a positive integer")
    parsed = int(text)
    if parsed <= 0:
        raise ValueError(f"B3 GetDetail {field_name} must be a positive integer")
    return parsed


def _date_br(value: object) -> date | None:
    text = _text(value)
    if text is None:
        return None
    return datetime.strptime(text, "%d/%m/%Y").date()


def _optional_bool(value: object) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    raise TypeError("B3 GetDetail boolean field has unexpected type")
