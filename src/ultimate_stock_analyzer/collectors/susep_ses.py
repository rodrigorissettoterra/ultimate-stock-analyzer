from __future__ import annotations

from dataclasses import dataclass

SUSEP_SES_HOME_URL = "https://www2.susep.gov.br/menuestatistica/SES/principal.aspx"
SUSEP_SES_DOWNLOAD_URL = "https://www2.susep.gov.br/redarq.asp?arq=BaseCompleta.zip"
SUSEP_LICENSED_ENTITIES_URL = (
    "https://www.gov.br/pt-br/servicos/consultar-entidades-licenciadas-pela-susep"
)
SUSEP_PRUDENTIAL_REGULATION_URL = (
    "https://www.gov.br/susep/pt-br/assuntos/informacoes-ao-mercado/"
    "solvencia-regulacao-prudencial-1/regulacao-contabil-e-auditoria"
)


@dataclass(frozen=True, slots=True)
class SusepSesSourceContract:
    """Source-level contract for SUSEP insurer evidence.

    This object deliberately describes only properties that are supported by the
    regulator's public pages. It does not claim that any scoring metric has already
    been mapped to a raw SES column.
    """

    source: str = "SUSEP_SES"
    source_kind: str = "OFFICIAL_PUBLIC"
    update_cadence: str = "WEEKLY"
    revision_aware: bool = False
    point_in_time_eligible: bool = False
    licensed_entity_registry_required: bool = True
    fuzzy_identity_matching_allowed: bool = False
    download_url: str = SUSEP_SES_DOWNLOAD_URL
    homepage_url: str = SUSEP_SES_HOME_URL


VERIFIED_SOURCE_TABLES = (
    "Ses_cias.csv",
    "Ses_seguros.csv",
    "Ses_pl_margem.csv",
    "Ses_seg_prov_det.csv",
    "ses_provramos.csv",
)


def source_contract() -> SusepSesSourceContract:
    return SusepSesSourceContract()
