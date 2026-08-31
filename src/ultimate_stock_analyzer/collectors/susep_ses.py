from __future__ import annotations

import re
from dataclasses import dataclass
from io import BytesIO
from pathlib import PurePosixPath
from zipfile import ZipFile

import httpx
import pandas as pd

SUSEP_SES_HOME_URL = "https://www2.susep.gov.br/menuestatistica/SES/principal.aspx"
SUSEP_SES_DOWNLOAD_URL = "https://www2.susep.gov.br/redarq.asp?arq=BaseCompleta.zip"
SUSEP_SES_TABLE_DOCUMENTATION_URL = (
    "https://www2.susep.gov.br/menuestatistica/SES/download/Documentacao_das_tabelas.rtf"
)
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
    table_documentation_url: str = SUSEP_SES_TABLE_DOCUMENTATION_URL


CANDIDATE_SOURCE_TABLES = (
    "Ses_cias.csv",
    "Ses_seguros.csv",
    "Ses_pl_margem.csv",
    "Ses_seg_prov_det.csv",
    "ses_provramos.csv",
)

CANDIDATE_DOCUMENTATION_FIELDS = (
    "damesano",
    "coenti",
    "premio_ganho",
    "sinistro_ocorrido",
    "desp_com",
    "plajustado",
    "cmr",
)

_RTF_HEX_ESCAPE_RE = re.compile(r"\\'([0-9a-fA-F]{2})")
_RTF_UNICODE_RE = re.compile(r"\\u(-?\d+)\??")
_RTF_CONTROL_WORD_RE = re.compile(r"\\[A-Za-z]+-?\d* ?")


def _rtf_unicode(match: re.Match[str]) -> str:
    value = int(match.group(1))
    if value < 0:
        value += 65536
    return chr(value)


def _rtf_to_plain_text(payload: bytes) -> str:
    """Extract searchable text from the official RTF without persisting the document."""

    text = payload.decode("latin1", errors="replace")
    text = _RTF_HEX_ESCAPE_RE.sub(
        lambda match: bytes.fromhex(match.group(1)).decode("cp1252", errors="replace"),
        text,
    )
    text = _RTF_UNICODE_RE.sub(_rtf_unicode, text)
    text = text.replace("\\par", "\n").replace("\\line", "\n").replace("\\tab", "\t")
    text = text.replace("\\{", "{").replace("\\}", "}").replace("\\\\", "\\")
    text = _RTF_CONTROL_WORD_RE.sub("", text)
    text = text.replace("{", " ").replace("}", " ")
    return " ".join(text.split())


@dataclass(slots=True)
class SusepSesCollector:
    """Download and inspect official SES evidence without inferring semantics."""

    user_agent: str = "ultimate-stock-analyzer/0.2"
    timeout_seconds: float = 120.0

    def _download(self, url: str) -> bytes:
        with httpx.Client(timeout=self.timeout_seconds, follow_redirects=True) as client:
            response = client.get(url, headers={"User-Agent": self.user_agent})
            response.raise_for_status()
        return response.content

    def download_archive_bytes(self) -> bytes:
        return self._download(SUSEP_SES_DOWNLOAD_URL)

    def download_table_documentation_bytes(self) -> bytes:
        return self._download(SUSEP_SES_TABLE_DOCUMENTATION_URL)

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

    def documentation_field_manifest(
        self,
        documentation: bytes,
        *,
        fields: tuple[str, ...] = CANDIDATE_DOCUMENTATION_FIELDS,
        context_chars: int = 180,
    ) -> dict[str, object]:
        """Extract bounded exact-token evidence from the official table documentation."""

        if context_chars < 40:
            raise ValueError("context_chars must be at least 40")
        text = _rtf_to_plain_text(documentation)
        folded = text.casefold()
        evidence: dict[str, dict[str, object]] = {}
        for field in fields:
            token = field.casefold()
            starts = [match.start() for match in re.finditer(re.escape(token), folded)]
            snippets: list[str] = []
            for start in starts[:3]:
                left = max(0, start - 40)
                right = min(len(text), start + len(field) + context_chars)
                snippets.append(text[left:right].strip())
            evidence[field] = {
                "present": bool(starts),
                "occurrences": len(starts),
                "snippets": snippets,
            }
        return {
            "source": "SUSEP_SES_TABLE_DOCUMENTATION",
            "source_url": SUSEP_SES_TABLE_DOCUMENTATION_URL,
            "fields": evidence,
        }


def source_contract() -> SusepSesSourceContract:
    return SusepSesSourceContract()
