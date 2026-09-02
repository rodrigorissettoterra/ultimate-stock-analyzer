from __future__ import annotations

import hashlib
import io
import re
import zipfile
from dataclasses import asdict, dataclass
from datetime import date, datetime
from typing import Any
from xml.etree import ElementTree

B3_CLASSIFICATION_CURRENT_SNAPSHOT_ONLY = "B3_CLASSIFICATION_CURRENT_SNAPSHOT_ONLY"
B3_CLASSIFICATION_AS_OF_CONTRACT_UNAVAILABLE = (
    "B3_CLASSIFICATION_AS_OF_CONTRACT_UNAVAILABLE"
)
B3_CLASSIFICATION_REVISION_HISTORY_UNAVAILABLE = (
    "B3_CLASSIFICATION_REVISION_HISTORY_UNAVAILABLE"
)
HISTORICAL_SECTOR_ROUTING_SOURCE_UNPROVEN = "HISTORICAL_SECTOR_ROUTING_SOURCE_UNPROVEN"

_DATE_PATTERNS = (
    re.compile(r"(?<!\d)(\d{4}-\d{2}-\d{2})(?!\d)"),
    re.compile(r"(?<!\d)(\d{2}/\d{2}/\d{4})(?!\d)"),
)


@dataclass(frozen=True, slots=True)
class B3SectorPITSourceAudit:
    collected_at: datetime
    source_page_url: str
    source_update_policy: str
    requested_start_year: int
    requested_end_year: int
    workbook_sha256: str
    workbook_size_bytes: int
    workbook_member_count: int
    classification_record_count: int
    core_properties_present: bool
    embedded_date_literals: tuple[str, ...]
    contractual_as_of_date: date | None
    immutable_historical_snapshot_urls: tuple[str, ...]
    historical_snapshot_count: int
    requested_years_covered: int
    current_snapshot_point_in_time_from_collection: bool
    historical_backfill_ready: bool
    sector_routing_point_in_time_ready: bool
    readiness_promotion_allowed: bool
    blockers: tuple[str, ...]
    effect: str = "diagnostic_only_sector_pit_source_no_routing_change"
    schema_version: str = "0.1"

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["collected_at"] = self.collected_at.isoformat()
        payload["contractual_as_of_date"] = (
            self.contractual_as_of_date.isoformat()
            if self.contractual_as_of_date is not None
            else None
        )
        payload["embedded_date_literals"] = list(self.embedded_date_literals)
        payload["immutable_historical_snapshot_urls"] = list(
            self.immutable_historical_snapshot_urls
        )
        payload["blockers"] = list(self.blockers)
        return payload


def audit_b3_sector_pit_source(
    *,
    workbook_content: bytes,
    classification_record_count: int,
    collected_at: datetime,
    source_page_url: str,
    requested_start_year: int,
    requested_end_year: int,
) -> B3SectorPITSourceAudit:
    if requested_start_year > requested_end_year:
        raise ValueError("requested_start_year must not be after requested_end_year")
    if classification_record_count <= 0:
        raise ValueError("classification_record_count must be positive")
    if not source_page_url.startswith("https://www.b3.com.br/"):
        raise ValueError("source_page_url must use the official B3 HTTPS host")
    if not workbook_content.startswith(b"PK"):
        raise ValueError("B3 classification workbook must be an XLSX archive")

    with zipfile.ZipFile(io.BytesIO(workbook_content)) as archive:
        member_names = tuple(sorted(archive.namelist()))
        required = {"xl/workbook.xml", "xl/worksheets/sheet1.xml"}
        missing = sorted(required - set(member_names))
        if missing:
            raise ValueError(f"B3 classification XLSX missing required members: {missing}")
        core_properties_present = "docProps/core.xml" in member_names
        searchable_text = "\n".join(
            _xml_text(archive.read(name))
            for name in member_names
            if name in {"docProps/core.xml", "xl/sharedStrings.xml", "xl/workbook.xml"}
        )

    date_literals = _date_literals(searchable_text)
    # No public B3 contract assigns an as-of meaning to an arbitrary date literal in this workbook.
    # A collection timestamp can start a forward snapshot ledger, but cannot backfill prior years.
    contractual_as_of_date = None
    immutable_historical_urls: tuple[str, ...] = ()
    blockers = (
        B3_CLASSIFICATION_AS_OF_CONTRACT_UNAVAILABLE,
        B3_CLASSIFICATION_CURRENT_SNAPSHOT_ONLY,
        B3_CLASSIFICATION_REVISION_HISTORY_UNAVAILABLE,
        HISTORICAL_SECTOR_ROUTING_SOURCE_UNPROVEN,
    )
    return B3SectorPITSourceAudit(
        collected_at=collected_at,
        source_page_url=source_page_url,
        source_update_policy="CURRENT_BASE_UPDATED_WEEKLY_ON_LAST_BUSINESS_DAY",
        requested_start_year=requested_start_year,
        requested_end_year=requested_end_year,
        workbook_sha256=hashlib.sha256(workbook_content).hexdigest(),
        workbook_size_bytes=len(workbook_content),
        workbook_member_count=len(member_names),
        classification_record_count=classification_record_count,
        core_properties_present=core_properties_present,
        embedded_date_literals=date_literals,
        contractual_as_of_date=contractual_as_of_date,
        immutable_historical_snapshot_urls=immutable_historical_urls,
        historical_snapshot_count=0,
        requested_years_covered=0,
        current_snapshot_point_in_time_from_collection=True,
        historical_backfill_ready=False,
        sector_routing_point_in_time_ready=False,
        readiness_promotion_allowed=False,
        blockers=blockers,
    )


def _xml_text(content: bytes) -> str:
    try:
        root = ElementTree.fromstring(content)
    except ElementTree.ParseError as error:
        raise ValueError("B3 classification workbook contains invalid XML") from error
    return "\n".join(text.strip() for text in root.itertext() if text.strip())


def _date_literals(value: str) -> tuple[str, ...]:
    dates: set[str] = set()
    for pattern in _DATE_PATTERNS:
        for match in pattern.findall(value):
            try:
                if "/" in match:
                    day, month, year = (int(part) for part in match.split("/"))
                    parsed = date(year, month, day)
                else:
                    parsed = date.fromisoformat(match)
            except ValueError:
                continue
            dates.add(parsed.isoformat())
    return tuple(sorted(dates))
