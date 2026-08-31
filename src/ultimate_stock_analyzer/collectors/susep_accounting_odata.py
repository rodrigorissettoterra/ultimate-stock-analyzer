from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

import httpx

from ultimate_stock_analyzer.collectors.susep_identity import normalize_cnpj

SUSEP_ACCOUNTING_DOCUMENTATION_URL = (
    "https://dados.susep.gov.br/olinda/servico/informacoescontabeis/versao/v1/documentacao"
)
SUSEP_ACCOUNTING_ODATA_ROOT = (
    "https://dados.susep.gov.br/olinda/servico/informacoescontabeis/versao/v1/odata"
)
VERIFIED_ACCOUNTING_RESOURCES = (
    "ContabeisAtivo",
    "ContabeisPassivo",
    "ContabeisDRE",
    "ContabeisDRER",
    "ContabeisDMPL",
    "ContabeisDMPS",
    "ContabeisDFCD",
    "ContabeisDFCI",
)


@dataclass(frozen=True, slots=True)
class SusepAccountingResource:
    """One exact entity-set entry from the official OData service document."""

    name: str
    url: str


@dataclass(frozen=True, slots=True)
class SusepAccountingRow:
    """One official SUSEP accounting observation from the Olinda API."""

    cnpj: str
    legal_name: str
    reference_month: date
    cmpid: int
    cmp_title: str
    value: Decimal
    source: str = "SUSEP_OLINDA_ACCOUNTING"
    point_in_time_eligible: bool = False


@dataclass(slots=True)
class SusepAccountingODataService:
    """Inspect and parse the official SUSEP accounting OData service fail-closed."""

    service_root: str = SUSEP_ACCOUNTING_ODATA_ROOT
    timeout_seconds: float = 120.0
    attempts: int = 3
    backoff_seconds: float = 2.0
    user_agent: str = "ultimate-stock-analyzer/0.2"

    def fetch_resource_catalog(self) -> tuple[SusepAccountingResource, ...]:
        """Return exact resource names and URLs from the OData service document."""

        payload = self._get_json(self.service_root, params={"$format": "json"})
        if not isinstance(payload, dict):
            raise TypeError("unexpected SUSEP accounting OData service-document shape")
        rows = payload.get("value")
        if not isinstance(rows, list):
            raise TypeError("unexpected SUSEP accounting OData service-document shape")

        resources: dict[str, SusepAccountingResource] = {}
        for row in rows:
            if not isinstance(row, dict):
                raise TypeError("unexpected SUSEP accounting OData resource entry shape")
            name = row.get("name")
            url = row.get("url")
            if not isinstance(name, str) or not name.strip():
                raise TypeError("SUSEP accounting OData resource has invalid name")
            if not isinstance(url, str) or not url.strip():
                raise TypeError("SUSEP accounting OData resource has invalid URL")
            normalized_name = name.strip()
            normalized_url = url.strip()
            existing = resources.get(normalized_name)
            if existing is not None and existing.url != normalized_url:
                raise ValueError("SUSEP accounting OData resource name has conflicting URLs")
            resources[normalized_name] = SusepAccountingResource(
                name=normalized_name,
                url=normalized_url,
            )
        if not resources:
            raise ValueError("SUSEP accounting OData service exposed no resources")
        return tuple(resources[name] for name in sorted(resources))

    def fetch_resource_names(self) -> tuple[str, ...]:
        """Return exact entity-set names exposed by the OData service document."""

        return tuple(resource.name for resource in self.fetch_resource_catalog())

    def verified_resources_present(self) -> bool:
        """Return whether every empirically verified canonical resource is exposed."""

        names = set(self.fetch_resource_names())
        return set(VERIFIED_ACCOUNTING_RESOURCES).issubset(names)

    def fetch_year_rows(
        self,
        resource: str,
        *,
        year: int,
        top: int | None = None,
    ) -> tuple[SusepAccountingRow, ...]:
        """Fetch one documented year-scoped accounting resource.

        SUSEP documents `Ano` as the required resource parameter. Olinda parameterized
        resources use the OData function form `Resource(Ano=@Ano)` with the alias
        supplied as `@Ano='YYYY'`. Optional `$top` is used only to bound smoke queries;
        production callers must explicitly decide whether complete pagination is needed.
        """

        if resource not in VERIFIED_ACCOUNTING_RESOURCES:
            raise ValueError("unverified SUSEP accounting resource")
        if year < 1999 or year > 2100:
            raise ValueError("year is outside supported SUSEP accounting range")
        if top is not None and top < 1:
            raise ValueError("top must be positive")

        url = f"{self.service_root}/{resource}(Ano=@Ano)"
        params: dict[str, Any] = {
            "@Ano": f"'{year}'",
            "$format": "json",
        }
        if top is not None:
            params["$top"] = top

        payload = self._get_json(url, params=params)
        rows = self._response_rows(payload)
        return tuple(self.parse_accounting_row(row) for row in rows)

    def _response_rows(self, payload: Any) -> list[dict[str, Any]]:
        if not isinstance(payload, dict):
            raise TypeError("unexpected SUSEP accounting OData response shape")
        rows = payload.get("value")
        if not isinstance(rows, list):
            raise TypeError("unexpected SUSEP accounting OData response shape")
        if not all(isinstance(row, dict) for row in rows):
            raise TypeError("unexpected SUSEP accounting OData row shape")
        return rows

    def parse_accounting_row(self, row: dict[str, Any]) -> SusepAccountingRow:
        """Parse documented accounting fields without inferring financial semantics."""

        legal_name = row.get("entnome")
        cnpj = row.get("cnpj")
        reference_month = row.get("mesreferencia")
        cmpid = row.get("cmpid")
        cmp_title = row.get("cmptitulo")
        value = row.get("valor")

        if not isinstance(legal_name, str) or not legal_name.strip():
            raise ValueError("SUSEP accounting row has invalid legal name")
        if not isinstance(cnpj, str):
            raise TypeError("SUSEP accounting row has invalid CNPJ")
        if not isinstance(cmp_title, str) or not cmp_title.strip():
            raise ValueError("SUSEP accounting row has invalid CMP title")

        normalized_cnpj = normalize_cnpj(cnpj)
        parsed_month = _parse_reference_month(reference_month)
        parsed_cmpid = _parse_cmpid(cmpid)
        parsed_value = _parse_decimal(value)
        return SusepAccountingRow(
            cnpj=normalized_cnpj,
            legal_name=legal_name.strip(),
            reference_month=parsed_month,
            cmpid=parsed_cmpid,
            cmp_title=cmp_title.strip(),
            value=parsed_value,
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
            raise RuntimeError("SUSEP accounting OData request failed without an error")
        raise last_error


def _parse_reference_month(value: Any) -> date:
    if not isinstance(value, str):
        raise TypeError("SUSEP accounting row has invalid reference month")
    text = value.strip()
    if len(text) < 7:
        raise ValueError("SUSEP accounting row has invalid reference month")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        try:
            parsed_date = date.fromisoformat(text[:10])
        except ValueError as exc:
            raise ValueError("SUSEP accounting row has invalid reference month") from exc
        return parsed_date.replace(day=1)
    return parsed.date().replace(day=1)


def _parse_cmpid(value: Any) -> int:
    if isinstance(value, bool):
        raise TypeError("SUSEP accounting row has invalid CMPID")
    try:
        result = int(value)
    except (TypeError, ValueError) as exc:
        raise TypeError("SUSEP accounting row has invalid CMPID") from exc
    if result <= 0:
        raise ValueError("SUSEP accounting row has invalid CMPID")
    return result


def _parse_decimal(value: Any) -> Decimal:
    if isinstance(value, bool) or value is None:
        raise TypeError("SUSEP accounting row has invalid value")
    try:
        result = Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError("SUSEP accounting row has invalid value") from exc
    if not result.is_finite():
        raise ValueError("SUSEP accounting row has non-finite value")
    return result
