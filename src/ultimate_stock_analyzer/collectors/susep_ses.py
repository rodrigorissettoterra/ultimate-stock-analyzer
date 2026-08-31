from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import PurePosixPath
from zipfile import ZipFile

import httpx
import pandas as pd

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


CANDIDATE_SOURCE_TABLES = (
    "Ses_cias.csv",
    "Ses_seguros.csv",
    "Ses_pl_margem.csv",
    "Ses_seg_prov_det.csv",
    "ses_provramos.csv",
)


@dataclass(slots=True)
class SusepSesCollector:
    """Download and inspect the official SES archive without inferring semantics."""

    user_agent: str = "ultimate-stock-analyzer/0.2"
    timeout_seconds: float = 120.0

    def download_archive_bytes(self) -> bytes:
        with httpx.Client(timeout=self.timeout_seconds, follow_redirects=True) as client:
            response = client.get(
                SUSEP_SES_DOWNLOAD_URL,
                headers={"User-Agent": self.user_agent},
            )
            response.raise_for_status()
        return response.content

    def list_csv_files(self, archive: bytes) -> list[str]:
        with ZipFile(BytesIO(archive)) as zf:
            return sorted(
                name
                for name in zf.namelist()
                if not name.endswith("/") and name.lower().endswith(".csv")
            )

    def find_table(self, archive: bytes, table_name: str) -> str:
        """Resolve one exact CSV basename, case-insensitively, or fail closed."""

        expected = table_name.casefold()
        matches = [
            name
            for name in self.list_csv_files(archive)
            if PurePosixPath(name).name.casefold() == expected
        ]
        if len(matches) != 1:
            raise ValueError(
                f"expected one exact SUSEP SES table named {table_name!r}, "
                f"found {len(matches)}"
            )
        return matches[0]

    def read_table(self, archive: bytes, table_name: str) -> pd.DataFrame:
        filename = self.find_table(archive, table_name)
        with ZipFile(BytesIO(archive)) as zf, zf.open(filename) as csv_file:
            return pd.read_csv(
                csv_file,
                sep=";",
                encoding="latin1",
                low_memory=False,
            )

    def inspect_schema(self, archive: bytes, table_name: str) -> tuple[str, ...]:
        """Return raw official column names without loading the full table."""

        filename = self.find_table(archive, table_name)
        with ZipFile(BytesIO(archive)) as zf, zf.open(filename) as csv_file:
            frame = pd.read_csv(
                csv_file,
                sep=";",
                encoding="latin1",
                nrows=0,
            )
        return tuple(str(column) for column in frame.columns)

    def candidate_schema_manifest(self, archive: bytes) -> dict[str, object]:
        """Inspect candidate tables and record presence/schema without semantic mapping."""

        csv_files = self.list_csv_files(archive)
        tables: dict[str, dict[str, object]] = {}
        for table_name in CANDIDATE_SOURCE_TABLES:
            try:
                filename = self.find_table(archive, table_name)
            except ValueError:
                tables[table_name] = {
                    "present": False,
                    "archive_path": None,
                    "columns": [],
                }
                continue
            tables[table_name] = {
                "present": True,
                "archive_path": filename,
                "columns": list(self.inspect_schema(archive, table_name)),
            }
        return {
            "source": "SUSEP_SES",
            "point_in_time_eligible": False,
            "csv_file_count": len(csv_files),
            "tables": tables,
        }


def source_contract() -> SusepSesSourceContract:
    return SusepSesSourceContract()
