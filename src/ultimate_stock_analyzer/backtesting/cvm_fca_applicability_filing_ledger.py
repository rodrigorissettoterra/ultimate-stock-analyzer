from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import zipfile
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime, time, timedelta
from typing import Any

FCA_APPLICABILITY_DETAIL_NOT_FOUND = "FCA_APPLICABILITY_DETAIL_NOT_FOUND"
FCA_APPLICABILITY_ROOT_JOIN_NOT_FOUND = "FCA_APPLICABILITY_ROOT_JOIN_NOT_FOUND"
FCA_APPLICABILITY_ROOT_JOIN_AMBIGUOUS = "FCA_APPLICABILITY_ROOT_JOIN_AMBIGUOUS"
FCA_APPLICABILITY_VERSION_MISMATCH = "FCA_APPLICABILITY_VERSION_MISMATCH"
FCA_APPLICABILITY_RECEIPT_DATE_MISSING = "FCA_APPLICABILITY_RECEIPT_DATE_MISSING"
FCA_APPLICABILITY_SECTOR_MISSING = "FCA_APPLICABILITY_SECTOR_MISSING"


@dataclass(frozen=True, slots=True)
class FCAApplicabilityFiling:
    cvm_code: int
    cnpj: str
    company_name: str
    reference_date: date
    version: int
    document_id: int
    received_date: date
    available_from: datetime
    sector_activity: str
    activity_description: str | None
    source_url: str
    archive_sha256: str
    evidence_sha256: str
    exact_document_join: bool = True
    point_in_time_eligible_from_available_from: bool = True

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["reference_date"] = self.reference_date.isoformat()
        payload["received_date"] = self.received_date.isoformat()
        payload["available_from"] = self.available_from.isoformat()
        return payload


@dataclass(frozen=True, slots=True)
class FCAApplicabilityFilingLedger:
    collected_at: datetime
    delivery_year: int
    source_url: str
    archive_sha256: str
    archive_size_bytes: int
    requested_cvm_codes: tuple[int, ...]
    root_filing_count: int
    applicability_detail_count: int
    filings: tuple[FCAApplicabilityFiling, ...]
    blockers: tuple[str, ...]
    readiness_promotion_allowed: bool = False
    effect: str = "fca_applicability_filing_ledger_no_readiness_promotion"
    schema_version: str = "0.1"

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["collected_at"] = self.collected_at.isoformat()
        payload["requested_cvm_codes"] = list(self.requested_cvm_codes)
        payload["filings"] = [filing.to_dict() for filing in self.filings]
        payload["blockers"] = list(self.blockers)
        return payload


def build_fca_applicability_filing_ledger(
    *,
    archive_content: bytes,
    collected_at: datetime,
    delivery_year: int,
    source_url: str,
    requested_cvm_codes: tuple[int, ...] | list[int],
) -> FCAApplicabilityFilingLedger:
    """Bind FCA general applicability rows to their exact root filing receipt dates.

    The current annual FCA archive may expose only a subset of historical detail revisions. Every
    detail row that is present is still independently usable from its own conservative
    ``available_from`` when its document/version identity joins exactly to the root filing ledger.
    This function does not infer missing older detail revisions and does not promote readiness.
    """
    if delivery_year < 2010:
        raise ValueError("FCA public archives are expected from 2010 onward")
    if not source_url.startswith("https://dados.cvm.gov.br/"):
        raise ValueError("FCA source_url must use the official CVM open-data HTTPS host")
    if not archive_content.startswith(b"PK"):
        raise ValueError("FCA source archive must be a ZIP file")
    requested = tuple(sorted({int(code) for code in requested_cvm_codes}))
    if not requested or any(code <= 0 for code in requested):
        raise ValueError("positive CVM codes are required")

    archive_sha = hashlib.sha256(archive_content).hexdigest()
    with zipfile.ZipFile(io.BytesIO(archive_content)) as archive:
        root_name = _single_member(archive.namelist(), f"fca_cia_aberta_{delivery_year}.csv")
        detail_name = _single_member(
            archive.namelist(), f"fca_cia_aberta_geral_{delivery_year}.csv"
        )
        root_rows = _read_rows(archive.read(root_name))
        detail_rows = _read_rows(archive.read(detail_name))

    requested_set = set(requested)
    root_by_document: dict[int, list[dict[str, str]]] = {}
    selected_root_rows: list[dict[str, str]] = []
    for row in root_rows:
        code = _int(row.get("CD_CVM"))
        document_id = _int(row.get("ID_DOC"))
        if code not in requested_set or document_id is None:
            continue
        selected_root_rows.append(row)
        root_by_document.setdefault(document_id, []).append(row)

    filings: list[FCAApplicabilityFiling] = []
    blockers: set[str] = set()
    selected_detail_count = 0
    for detail in detail_rows:
        code = _int(detail.get("Codigo_CVM"))
        if code not in requested_set:
            continue
        selected_detail_count += 1
        document_id = _int(detail.get("ID_Documento"))
        if document_id is None:
            blockers.add(FCA_APPLICABILITY_ROOT_JOIN_NOT_FOUND)
            continue
        matches = root_by_document.get(document_id, [])
        if not matches:
            blockers.add(FCA_APPLICABILITY_ROOT_JOIN_NOT_FOUND)
            continue
        if len(matches) != 1:
            blockers.add(FCA_APPLICABILITY_ROOT_JOIN_AMBIGUOUS)
            continue
        root = matches[0]
        detail_version = _int(detail.get("Versao"))
        root_version = _int(root.get("VERSAO"))
        if detail_version is None or root_version is None or detail_version != root_version:
            blockers.add(FCA_APPLICABILITY_VERSION_MISMATCH)
            continue
        received_date = _date(root.get("DT_RECEB"))
        if received_date is None:
            blockers.add(FCA_APPLICABILITY_RECEIPT_DATE_MISSING)
            continue
        sector = str(detail.get("Setor_Atividade") or "").strip()
        if not sector:
            blockers.add(FCA_APPLICABILITY_SECTOR_MISSING)
            continue
        reference_date = _date(detail.get("Data_Referencia"))
        if reference_date is None:
            raise ValueError("FCA applicability detail row has no Data_Referencia")
        cnpj = _digits(detail.get("CNPJ_Companhia"))
        if not cnpj:
            raise ValueError("FCA applicability detail row has no CNPJ_Companhia")
        company_name = str(detail.get("Nome_Empresarial") or "").strip()
        if not company_name:
            raise ValueError("FCA applicability detail row has no Nome_Empresarial")
        available_from = datetime.combine(
            received_date + timedelta(days=1), time.min, tzinfo=UTC
        )
        activity_description = str(detail.get("Descricao_Atividade") or "").strip() or None
        evidence_payload = {
            "archive_sha256": archive_sha,
            "cvm_code": code,
            "cnpj": cnpj,
            "document_id": document_id,
            "version": detail_version,
            "reference_date": reference_date.isoformat(),
            "received_date": received_date.isoformat(),
            "sector_activity": sector,
            "activity_description": activity_description,
        }
        evidence_sha = hashlib.sha256(
            json.dumps(
                evidence_payload,
                sort_keys=True,
                ensure_ascii=False,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        filings.append(
            FCAApplicabilityFiling(
                cvm_code=code,
                cnpj=cnpj,
                company_name=company_name,
                reference_date=reference_date,
                version=detail_version,
                document_id=document_id,
                received_date=received_date,
                available_from=available_from,
                sector_activity=sector,
                activity_description=activity_description,
                source_url=source_url,
                archive_sha256=archive_sha,
                evidence_sha256=evidence_sha,
            )
        )

    if selected_detail_count == 0:
        blockers.add(FCA_APPLICABILITY_DETAIL_NOT_FOUND)
    return FCAApplicabilityFilingLedger(
        collected_at=collected_at,
        delivery_year=delivery_year,
        source_url=source_url,
        archive_sha256=archive_sha,
        archive_size_bytes=len(archive_content),
        requested_cvm_codes=requested,
        root_filing_count=len(selected_root_rows),
        applicability_detail_count=selected_detail_count,
        filings=tuple(
            sorted(
                filings,
                key=lambda item: (
                    item.cvm_code,
                    item.reference_date,
                    item.available_from,
                    item.version,
                ),
            )
        ),
        blockers=tuple(sorted(blockers)),
    )


def _single_member(names: list[str], expected_basename: str) -> str:
    matches = [name for name in names if name.rsplit("/", 1)[-1] == expected_basename]
    if len(matches) != 1:
        raise ValueError(f"expected one FCA member {expected_basename!r}, found {len(matches)}")
    return matches[0]


def _read_rows(content: bytes) -> list[dict[str, str]]:
    text = content.decode("latin-1")
    reader = csv.DictReader(io.StringIO(text), delimiter=";")
    return [
        {
            str(key).strip(): str(value or "").strip()
            for key, value in row.items()
            if key
        }
        for row in reader
    ]


def _int(value: object) -> int | None:
    digits = _digits(value)
    return int(digits) if digits else None


def _digits(value: object) -> str:
    return re.sub(r"\D", "", str(value or "").strip())


def _date(value: object) -> date | None:
    text = str(value or "").strip()
    if not text:
        return None
    return date.fromisoformat(text[:10])
