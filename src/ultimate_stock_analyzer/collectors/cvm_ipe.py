from __future__ import annotations

import csv
import io
import zipfile
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime, time, timedelta
from typing import Any
from urllib.parse import urlparse

import httpx

CVM_IPE_BASE_URL = "https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/IPE/DADOS"
CVM_IPE_REQUIRED_COLUMNS = frozenset(
    {
        "CNPJ_Companhia",
        "Nome_Companhia",
        "Codigo_CVM",
        "Data_Referencia",
        "Categoria",
        "Tipo",
        "Especie",
        "Assunto",
        "Data_Entrega",
        "Tipo_Apresentacao",
        "Protocolo_Entrega",
        "Versao",
        "Link_Download",
    }
)


@dataclass(frozen=True, slots=True)
class CVMIPEDocument:
    company_id: str
    cvm_code: int
    company_name: str
    cnpj: str | None
    reference_date: date
    delivered_on: date
    available_from: datetime
    category: str
    document_type: str | None
    species: str | None
    subject: str | None
    presentation_type: str | None
    delivery_protocol: str | None
    version: int | None
    download_url: str | None
    source_year: int

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["reference_date"] = self.reference_date.isoformat()
        payload["delivered_on"] = self.delivered_on.isoformat()
        payload["available_from"] = self.available_from.isoformat()
        return payload


@dataclass(slots=True)
class CVMIPECollector:
    timeout_seconds: float = 60.0
    user_agent: str = "ultimate-stock-analyzer/1.0"

    def dataset_url(self, year: int) -> str:
        if year < 2003:
            raise ValueError("CVM IPE annual history starts in 2003")
        return f"{CVM_IPE_BASE_URL}/ipe_cia_aberta_{year}.zip"

    def fetch_year(
        self,
        year: int,
        *,
        cvm_codes: set[int] | frozenset[int] | None = None,
    ) -> tuple[CVMIPEDocument, ...]:
        url = self.dataset_url(year)
        parsed = urlparse(url)
        if parsed.scheme != "https" or parsed.hostname != "dados.cvm.gov.br":
            raise ValueError("CVM IPE collector only accepts official dados.cvm.gov.br HTTPS URLs")
        with httpx.Client(timeout=self.timeout_seconds, follow_redirects=True) as client:
            response = client.get(url, headers={"User-Agent": self.user_agent})
            response.raise_for_status()
        return parse_cvm_ipe_zip(response.content, year=year, cvm_codes=cvm_codes)


def parse_cvm_ipe_zip(
    content: bytes,
    *,
    year: int,
    cvm_codes: set[int] | frozenset[int] | None = None,
) -> tuple[CVMIPEDocument, ...]:
    if year < 2003:
        raise ValueError("CVM IPE annual history starts in 2003")
    normalized_codes = None
    if cvm_codes is not None:
        normalized_codes = frozenset(_positive_int(value, "cvm_codes") for value in cvm_codes)

    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        members = [name for name in archive.namelist() if name.lower().endswith(".csv")]
        if len(members) != 1:
            raise ValueError(f"expected exactly one CVM IPE CSV, found {len(members)}")
        raw = archive.read(members[0])

    text = _decode_cvm(raw)
    reader = csv.DictReader(io.StringIO(text), delimiter=";")
    columns = frozenset(reader.fieldnames or ())
    missing = sorted(CVM_IPE_REQUIRED_COLUMNS - columns)
    if missing:
        raise ValueError(f"CVM IPE schema missing required columns: {missing}")

    documents: list[CVMIPEDocument] = []
    for row_number, row in enumerate(reader, start=2):
        code_text = _optional_text(row.get("Codigo_CVM"))
        if code_text is None:
            if normalized_codes is None:
                raise ValueError(f"CVM IPE row {row_number} has no Codigo_CVM")
            continue
        try:
            cvm_code = _positive_int(code_text, "Codigo_CVM")
        except ValueError:
            if normalized_codes is None:
                raise ValueError(f"CVM IPE row {row_number} has invalid Codigo_CVM") from None
            continue
        if normalized_codes is not None and cvm_code not in normalized_codes:
            continue
        try:
            reference_date = _required_date(row.get("Data_Referencia"), "Data_Referencia")
            delivered_on = _required_date(row.get("Data_Entrega"), "Data_Entrega")
            company_name = _required_text(row.get("Nome_Companhia"), "Nome_Companhia")
            category = _required_text(row.get("Categoria"), "Categoria")
        except ValueError as error:
            raise ValueError(f"invalid CVM IPE target row {row_number}: {error}") from error

        documents.append(
            CVMIPEDocument(
                company_id=f"cvm:{cvm_code}",
                cvm_code=cvm_code,
                company_name=company_name,
                cnpj=_optional_text(row.get("CNPJ_Companhia")),
                reference_date=reference_date,
                delivered_on=delivered_on,
                available_from=_conservative_availability(delivered_on),
                category=category,
                document_type=_optional_text(row.get("Tipo")),
                species=_optional_text(row.get("Especie")),
                subject=_optional_text(row.get("Assunto")),
                presentation_type=_optional_text(row.get("Tipo_Apresentacao")),
                delivery_protocol=_optional_text(row.get("Protocolo_Entrega")),
                version=_optional_positive_int(row.get("Versao")),
                download_url=_optional_official_download_url(row.get("Link_Download")),
                source_year=year,
            )
        )
    return tuple(
        sorted(
            documents,
            key=lambda item: (
                item.cvm_code,
                item.reference_date,
                item.delivered_on,
                item.category,
                item.document_type or "",
                item.delivery_protocol or "",
            ),
        )
    )


def _conservative_availability(delivered_on: date) -> datetime:
    return datetime.combine(delivered_on + timedelta(days=1), time.min, tzinfo=UTC)


def _decode_cvm(content: bytes) -> str:
    for encoding in ("utf-8-sig", "cp1252", "latin1"):
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ValueError("unable to decode CVM IPE CSV")


def _required_date(value: Any, field: str) -> date:
    text = _required_text(value, field)
    try:
        return date.fromisoformat(text[:10])
    except ValueError as error:
        raise ValueError(f"{field} must be an ISO date") from error


def _positive_int(value: Any, field: str) -> int:
    try:
        parsed = int(str(value).strip())
    except (TypeError, ValueError) as error:
        raise ValueError(f"{field} must be a positive integer") from error
    if parsed <= 0:
        raise ValueError(f"{field} must be a positive integer")
    return parsed


def _optional_positive_int(value: Any) -> int | None:
    text = _optional_text(value)
    if text is None:
        return None
    try:
        parsed = int(text)
    except ValueError as error:
        raise ValueError("Versao must be a positive integer when present") from error
    if parsed <= 0:
        raise ValueError("Versao must be a positive integer when present")
    return parsed


def _optional_official_download_url(value: Any) -> str | None:
    text = _optional_text(value)
    if text is None:
        return None
    parsed = urlparse(text)
    if parsed.scheme != "https" or parsed.hostname not in {"www.rad.cvm.gov.br", "rad.cvm.gov.br"}:
        raise ValueError("Link_Download must use an official CVM RAD HTTPS host")
    return text


def _required_text(value: Any, field: str) -> str:
    text = _optional_text(value)
    if text is None:
        raise ValueError(f"{field} must not be blank")
    return text


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
