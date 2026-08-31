from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

import httpx

from ultimate_stock_analyzer.collectors.susep_identity import normalize_cnpj

SUSEP_PROVISIONS_DOCUMENTATION_URL = (
    "https://dados.susep.gov.br/olinda/servico/provisoes/versao/v1/documentacao"
)
SUSEP_PROVISIONS_ODATA_ROOT = (
    "https://dados.susep.gov.br/olinda/servico/provisoes/versao/v1/odata"
)


@dataclass(frozen=True, slots=True)
class SusepProvisionsResource:
    """One exact resource entry from the official provisions service document."""

    name: str
    url: str


@dataclass(frozen=True, slots=True)
class SusepProvisionRow:
    """One official SUSEP technical-provision balance observation."""

    cnpj: str
    legal_name: str
    reference_month: date
    provision: str
    value: Decimal
    group: str | None = None
    branch: str | None = None
    source: str = "SUSEP_OLINDA_PROVISIONS"
    point_in_time_eligible: bool = False


@dataclass(slots=True)
class SusepProvisionsODataService:
    """Inspect and parse SUSEP technical-provision data fail-closed."""

    service_root: str = SUSEP_PROVISIONS_ODATA_ROOT
    timeout_seconds: float = 120.0
    attempts: int = 3
    backoff_seconds: float = 2.0
    user_agent: str = "ultimate-stock-analyzer/0.2"

    def fetch_resource_catalog(self) -> tuple[SusepProvisionsResource, ...]:
        payload = self._get_json(self.service_root, params={"$format": "json"})
        if not isinstance(payload, dict):
            raise TypeError("unexpected SUSEP provisions OData service-document shape")
        rows = payload.get("value")
        if not isinstance(rows, list):
            raise TypeError("unexpected SUSEP provisions OData service-document shape")

        resources: dict[str, SusepProvisionsResource] = {}
        for row in rows:
            if not isinstance(row, dict):
                raise TypeError("unexpected SUSEP provisions resource entry shape")
            name = row.get("name")
            url = row.get("url")
            if not isinstance(name, str) or not name.strip():
                raise TypeError("SUSEP provisions resource has invalid name")
            if not isinstance(url, str) or not url.strip():
                raise TypeError("SUSEP provisions resource has invalid URL")
            normalized_name = name.strip()
            normalized_url = url.strip()
            existing = resources.get(normalized_name)
            if existing is not None and existing.url != normalized_url:
                raise ValueError("SUSEP provisions resource name has conflicting URLs")
            resources[normalized_name] = SusepProvisionsResource(
                name=normalized_name,
                url=normalized_url,
            )
        if not resources:
            raise ValueError("SUSEP provisions OData service exposed no resources")
        return tuple(resources[name] for name in sorted(resources))

    def parse_provision_row(self, row: dict[str, Any]) -> SusepProvisionRow:
        legal_name = row.get("entnome")
        cnpj = row.get("cnpj")
        reference_month = row.get("mesreferencia")
        provision = row.get("provisao")
        value = row.get("valor")
        group = row.get("grupo")
        branch = row.get("ramo")

        if not isinstance(legal_name, str) or not legal_name.strip():
            raise ValueError("SUSEP provision row has invalid legal name")
        if not isinstance(cnpj, str):
            raise TypeError("SUSEP provision row has invalid CNPJ")
        if not isinstance(provision, str) or not provision.strip():
            raise ValueError("SUSEP provision row has invalid provision name")
        if group is not None and not isinstance(group, str):
            raise TypeError("SUSEP provision row has invalid group")
        if branch is not None and not isinstance(branch, str):
            raise TypeError("SUSEP provision row has invalid branch")

        return SusepProvisionRow(
            cnpj=normalize_cnpj(cnpj),
            legal_name=legal_name.strip(),
            reference_month=_parse_reference_month(reference_month),
            provision=provision.strip(),
            value=_parse_decimal(value),
            group=None if group is None else group.strip() or None,
            branch=None if branch is None else branch.strip() or None,
        )

    def _get_json(self, url: str, *, params: dict[str, Any]) -> Any:
        if self.attempts < 1:
            raise ValueError("attempts must be positive")
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if self.backoff_seconds < 0:
            raise ValueError("backoff_seconds must be non-negative")

        last_error: Exception | None = None
        timeout = httpx.Timeout(self.timeout_seconds, connect=min(30.0, self.timeout_seconds))
        with httpx.Client(
            timeout=timeout,
            follow_redirects=True,
            headers={"User-Agent": self.user_agent},
        ) as client:
            for attempt in range(1, self.attempts + 1):
                try:
                    response = client.get(url, params=params)
                    response.raise_for_status()
                    return response.json()
                except httpx.HTTPStatusError as exc:
                    status = exc.response.status_code
                    if status != 429 and status < 500:
                        raise
                    last_error = exc
                except httpx.RequestError as exc:
                    last_error = exc
                if attempt < self.attempts and self.backoff_seconds:
                    time.sleep(self.backoff_seconds * (2 ** (attempt - 1)))

        if last_error is None:
            raise RuntimeError("SUSEP provisions OData request failed without an error")
        raise last_error


def _parse_reference_month(value: Any) -> date:
    if not isinstance(value, str):
        raise TypeError("SUSEP provision row has invalid reference month")
    text = value.strip()
    if len(text) < 7:
        raise ValueError("SUSEP provision row has invalid reference month")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        try:
            parsed_date = date.fromisoformat(text[:10])
        except ValueError as exc:
            raise ValueError("SUSEP provision row has invalid reference month") from exc
        return parsed_date.replace(day=1)
    return parsed.date().replace(day=1)


def _parse_decimal(value: Any) -> Decimal:
    if isinstance(value, bool) or value is None:
        raise TypeError("SUSEP provision row has invalid value")
    try:
        result = Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError("SUSEP provision row has invalid value") from exc
    if not result.is_finite():
        raise ValueError("SUSEP provision row has non-finite value")
    return result
