from __future__ import annotations

from dataclasses import dataclass

SUSEP_LICENSED_ENTITIES_URL = (
    "https://www2.susep.gov.br/menuatendimento/procura_2011.asp"
)


@dataclass(frozen=True, slots=True)
class SusepLicensedEntityRecord:
    """Exact identity evidence from SUSEP's licensed-entities registry.

    SUSEP's public registry exposes both CNPJ and Código FIP for supervised entities.
    This record intentionally stores only fields needed for deterministic identity
    resolution. Names are evidence/display metadata and are never matching keys.
    """

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
    """Resolve supervised entities by exact official CNPJ only.

    One listed issuer may legitimately relate to more than one supervised insurer, so
    the contract returns every exact CNPJ match rather than assuming one-to-one
    identity. Matching by ticker, company name, substring or fuzzy similarity is
    intentionally forbidden.
    """

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
