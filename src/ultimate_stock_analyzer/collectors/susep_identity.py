from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

SUSEP_LICENSED_ENTITIES_URL = (
    "https://www2.susep.gov.br/menuatendimento/procura_2011.asp"
)
SUSEP_OLINDA_IDENTITY_URL = (
    "https://dados.susep.gov.br/olinda/servico/empresas/versao/v1/odata/DadosCadastrais"
)


@dataclass(frozen=True, slots=True)
class SusepLicensedEntityRecord:
    """Exact identity evidence from SUSEP's public entity registry/API."""

    legal_name: str
    cnpj: str
    fip_code: str
    entity_type: str | None = None
    source: str = "SUSEP_LICENSED_ENTITIES"
    source_url: str = SUSEP_LICENSED_ENTITIES_URL

    @property
    def normalized_cnpj(self) -> str:
        return normalize_cnpj(self.cnpj)

    @property
    def normalized_fip_code(self) -> str:
        return normalize_fip_code(self.fip_code)


def normalize_cnpj(value: str) -> str:
    """Normalize a CNPJ to exactly fourteen digits or fail closed."""

    digits = "".join(character for character in value if character.isdigit())
    if len(digits) != 14:
        raise ValueError("CNPJ must contain exactly 14 digits")
    return digits


def normalize_fip_code(value: str) -> str:
    """Normalize a SUSEP/FIP company code while preserving leading zeroes."""

    stripped = value.strip()
    if not stripped or not stripped.isdigit():
        raise ValueError("SUSEP FIP code must contain only digits")
    return stripped


def match_susep_entities_by_cnpj(
    issuer_cnpj: str,
    records: list[SusepLicensedEntityRecord] | tuple[SusepLicensedEntityRecord, ...],
) -> tuple[SusepLicensedEntityRecord, ...]:
    """Resolve supervised entities by exact official CNPJ only."""

    target = normalize_cnpj(issuer_cnpj)
    matches: dict[tuple[str, str], SusepLicensedEntityRecord] = {}
    for record in records:
        if record.normalized_cnpj != target:
            continue
        key = (record.normalized_cnpj, record.normalized_fip_code)
        matches[key] = record
    return tuple(matches[key] for key in sorted(matches))


def matched_susep_fip_codes(
    issuer_cnpj: str,
    records: list[SusepLicensedEntityRecord] | tuple[SusepLicensedEntityRecord, ...],
) -> tuple[str, ...]:
    """Return deterministic exact SUSEP/FIP codes for one issuer CNPJ."""

    return tuple(
        record.normalized_fip_code
        for record in match_susep_entities_by_cnpj(issuer_cnpj, records)
    )


@dataclass(slots=True)
class SusepOlindaIdentityCollector:
    """Read official SUSEP Olinda entity identity data without fuzzy matching.

    The official service documents `entcodigofip`, `entnome` and `entcgc` as Código
    FIP, legal name and CNPJ. The collector pages through those public fields, validates
    every returned identity row and leaves issuer matching to the exact-CNPJ contract
    above. It never searches by company name or ticker.
    """

    endpoint: str = SUSEP_OLINDA_IDENTITY_URL
    timeout_seconds: float = 30.0
    page_size: int = 500
    max_pages: int = 20
    user_agent: str = "ultimate-stock-analyzer/0.2"

    def fetch_records(self) -> tuple[SusepLicensedEntityRecord, ...]:
        if self.page_size < 1:
            raise ValueError("page_size must be positive")
        if self.max_pages < 1:
            raise ValueError("max_pages must be positive")

        records: list[SusepLicensedEntityRecord] = []
        with httpx.Client(
            timeout=self.timeout_seconds,
            follow_redirects=True,
            headers={"User-Agent": self.user_agent},
        ) as client:
            for page in range(self.max_pages):
                rows = self._fetch_page(client, skip=page * self.page_size)
                records.extend(self._parse_row(row) for row in rows)
                if len(rows) < self.page_size:
                    return tuple(records)

        raise RuntimeError("SUSEP Olinda identity pagination exceeded max_pages")

    def fetch_by_cnpj(self, issuer_cnpj: str) -> tuple[SusepLicensedEntityRecord, ...]:
        """Fetch the public registry and return exact CNPJ matches only."""

        return match_susep_entities_by_cnpj(issuer_cnpj, self.fetch_records())

    def _fetch_page(self, client: httpx.Client, *, skip: int) -> list[dict[str, Any]]:
        response = client.get(
            self.endpoint,
            params={
                "$format": "json",
                "$select": "mercodigo,entcodigofip,entnome,entcgc",
                "$orderby": "entcodigofip asc",
                "$skip": skip,
                "$top": self.page_size,
            },
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict) or not isinstance(payload.get("value"), list):
            raise ValueError("unexpected SUSEP Olinda identity response shape")
        rows = payload["value"]
        if not all(isinstance(row, dict) for row in rows):
            raise ValueError("unexpected SUSEP Olinda identity row shape")
        return rows

    def _parse_row(self, row: dict[str, Any]) -> SusepLicensedEntityRecord:
        name = row.get("entnome")
        cnpj = row.get("entcgc")
        fip_code = row.get("entcodigofip")
        market_code = row.get("mercodigo")
        if not isinstance(name, str) or not name.strip():
            raise ValueError("SUSEP Olinda identity row has invalid legal name")
        if not isinstance(cnpj, str):
            raise ValueError("SUSEP Olinda identity row has invalid CNPJ")
        if not isinstance(fip_code, str):
            raise ValueError("SUSEP Olinda identity row has invalid FIP code")

        normalized_cnpj = normalize_cnpj(cnpj)
        normalized_fip = normalize_fip_code(fip_code)
        entity_type = None if market_code is None else str(market_code).strip()
        return SusepLicensedEntityRecord(
            legal_name=name.strip(),
            cnpj=normalized_cnpj,
            fip_code=normalized_fip,
            entity_type=entity_type,
            source="SUSEP_OLINDA_EMPRESAS",
            source_url=self.endpoint,
        )
