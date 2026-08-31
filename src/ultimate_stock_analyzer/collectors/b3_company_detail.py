from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

import httpx

B3_COMPANY_API_BASE = (
    "https://sistemaswebb3-listados.b3.com.br/"
    "listedCompaniesProxy/CompanyCall"
)
B3_LISTED_COMPANIES_PAGE = (
    "https://sistemaswebb3-listados.b3.com.br/"
    "listedCompaniesPage/?language=pt-br"
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
    issuer_code: str | None
    primary_code: str | None
    security_codes: tuple[B3ListedSecurityCode, ...]
    share_quotation_start: date | None
    collected_at: datetime
    source: str = "B3_LISTED_COMPANIES_GET_DETAIL"

    @property
    def all_security_codes(self) -> tuple[str, ...]:
        values = [self.primary_code] if self.primary_code else []
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
        with httpx.Client(
            timeout=self.timeout_seconds,
            follow_redirects=True,
            headers=headers,
        ) as client:
            for attempt in range(1, self.max_attempts + 1):
                try:
                    response = client.get(self.detail_url(cvm_code))
                except httpx.TransportError:
                    if attempt == self.max_attempts:
                        raise
                    continue
                retryable = response.status_code == 429 or response.status_code >= 500
                if retryable and attempt < self.max_attempts:
                    continue
                response.raise_for_status()
                return self.parse(
                    response.json(),
                    expected_cvm_code=cvm_code,
                    collected_at=collected_at,
                )
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
        other_codes = payload.get("otherCodes") or []
        if not isinstance(other_codes, list):
            raise TypeError("B3 GetDetail otherCodes must be a list")
        securities: list[B3ListedSecurityCode] = []
        for item in other_codes:
            if not isinstance(item, dict):
                raise TypeError("B3 GetDetail otherCodes item must be an object")
            code = _upper(item.get("code"))
            if code:
                securities.append(B3ListedSecurityCode(code, _text(item.get("isin"))))
        return B3ListedCompanyDetail(
            company_id=f"cvm:{returned_cvm}",
            cvm_code=returned_cvm,
            cnpj=_digits(payload.get("cnpj")),
            issuer_code=_upper(payload.get("issuingCompany")),
            primary_code=_upper(payload.get("code")),
            security_codes=tuple(securities),
            share_quotation_start=_date_br(payload.get("dateQuotation")),
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
    if text is None or not text.isdigit() or int(text) <= 0:
        raise ValueError(f"B3 GetDetail {field_name} must be a positive integer")
    return int(text)


def _date_br(value: object) -> date | None:
    text = _text(value)
    if text is None:
        return None
    day, month, year = (int(part) for part in text.split("/"))
    return date(year, month, day)
