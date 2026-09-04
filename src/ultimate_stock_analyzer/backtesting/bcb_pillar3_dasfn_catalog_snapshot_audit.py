from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any
from urllib.parse import parse_qs, urlparse

from ultimate_stock_analyzer.backtesting.bcb_pillar3_dasfn_pit_source_audit import (
    BANK_EVIDENCE_NOT_POINT_IN_TIME,
    PILLAR3_DASFN_HISTORICAL_VINTAGE_QUERY_UNPROVEN,
    PILLAR3_DASFN_PAYLOAD_PUBLICATION_TIMESTAMP_UNPROVEN,
    PILLAR3_DASFN_REVISION_HISTORY_UNPROVEN,
    PILLAR3_DASFN_STRUCTURED_COVERAGE_GAP,
)

PILLAR3_DASFN_CATALOG_PAGE_UNAVAILABLE = "PILLAR3_DASFN_CATALOG_PAGE_UNAVAILABLE"
PILLAR3_DASFN_CATALOG_SNAPSHOT_INCOMPLETE = "PILLAR3_DASFN_CATALOG_SNAPSHOT_INCOMPLETE"
PILLAR3_DASFN_CATALOG_SNAPSHOT_CONTRACT_UNUSABLE = (
    "PILLAR3_DASFN_CATALOG_SNAPSHOT_CONTRACT_UNUSABLE"
)
PILLAR3_DASFN_LOCAL_FILTER_NO_ROWS = "PILLAR3_DASFN_LOCAL_FILTER_NO_ROWS"
PILLAR3_DASFN_LOCAL_FILTER_ROW_UNUSABLE = "PILLAR3_DASFN_LOCAL_FILTER_ROW_UNUSABLE"
PILLAR3_DASFN_SNAPSHOT_FINAL_URL_UNTRUSTED = (
    "PILLAR3_DASFN_SNAPSHOT_FINAL_URL_UNTRUSTED"
)

_DASFN_CATALOG_HOST = "https://olinda.bcb.gov.br/"
_DASFN_CATALOG_ENDPOINT = (
    "https://olinda.bcb.gov.br/olinda/servico/"
    "DASFN/versao/v1/odata/Recursos"
)
_REQUIRED_CENTRAL_FIELDS = (
    "Api",
    "Versao",
    "CnpjInstituicao",
    "Recurso",
    "URLDados",
)
_CENTRAL_SELECT = ",".join(_REQUIRED_CENTRAL_FIELDS)


@dataclass(frozen=True, slots=True)
class Pillar3DASFNCatalogPageInput:
    skip: int
    top: int
    requested_url: str
    final_url: str | None
    status_code: int | None
    content_type: str | None
    content: bytes | None
    transport_error: str | None = None


@dataclass(frozen=True, slots=True)
class Pillar3DASFNCatalogPageEvidence:
    skip: int
    top: int
    requested_url: str
    final_url: str | None
    status_code: int | None
    content_type: str | None
    sha256: str | None
    size_bytes: int
    row_count: int | None
    transport_error: str | None
    trusted_http_success: bool
    central_contract_usable: bool


@dataclass(frozen=True, slots=True)
class Pillar3DASFNCatalogRow:
    cnpj_instituicao: str
    api: str
    versao: str
    recurso: str
    url_dados: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class BCBPillar3DASFNCatalogSnapshotAudit:
    collected_at: datetime
    catalog_source_url: str
    pages: tuple[Pillar3DASFNCatalogPageEvidence, ...]
    total_catalog_rows: int
    pillar3_rows: tuple[Pillar3DASFNCatalogRow, ...]
    observed_version_families: tuple[str, ...]
    observed_versions: tuple[str, ...]
    observed_resources: tuple[str, ...]
    observed_institutions: tuple[str, ...]
    snapshot_complete: bool
    central_contract_usable: bool
    local_filter_usable: bool
    current_catalog_discovery_ready: bool
    historical_vintage_query_proven: bool
    historical_replay_ready: bool
    bank_evidence_point_in_time_ready: bool
    readiness_promotion_allowed: bool
    blockers: tuple[str, ...]
    effect: str = "diagnostic_only_dasfn_unfiltered_snapshot_no_readiness_change"
    schema_version: str = "0.1"

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "effect": self.effect,
            "collected_at": self.collected_at.isoformat(),
            "catalog_source_url": self.catalog_source_url,
            "pages": [asdict(item) for item in self.pages],
            "total_catalog_rows": self.total_catalog_rows,
            "pillar3_rows": [item.to_dict() for item in self.pillar3_rows],
            "observed_version_families": list(self.observed_version_families),
            "observed_versions": list(self.observed_versions),
            "observed_resources": list(self.observed_resources),
            "observed_institutions": list(self.observed_institutions),
            "snapshot_complete": self.snapshot_complete,
            "central_contract_usable": self.central_contract_usable,
            "local_filter_usable": self.local_filter_usable,
            "current_catalog_discovery_ready": self.current_catalog_discovery_ready,
            "historical_vintage_query_proven": self.historical_vintage_query_proven,
            "historical_replay_ready": self.historical_replay_ready,
            "bank_evidence_point_in_time_ready": self.bank_evidence_point_in_time_ready,
            "readiness_promotion_allowed": self.readiness_promotion_allowed,
            "blockers": list(self.blockers),
        }


def audit_bcb_pillar3_dasfn_catalog_snapshot(
    *,
    pages: tuple[Pillar3DASFNCatalogPageInput, ...]
    | list[Pillar3DASFNCatalogPageInput],
    collected_at: datetime,
    catalog_source_url: str,
) -> BCBPillar3DASFNCatalogSnapshotAudit:
    if collected_at.tzinfo is None or collected_at.utcoffset() is None:
        raise ValueError("collected_at must be timezone-aware")
    if catalog_source_url.rstrip("/") != _DASFN_CATALOG_ENDPOINT:
        raise ValueError("catalog_source_url must be the official BCB DASFN Recursos endpoint")

    normalized = tuple(pages)
    if not normalized:
        raise ValueError("pages must contain at least one catalog response")
    _validate_page_sequence(normalized)

    evidence: list[Pillar3DASFNCatalogPageEvidence] = []
    catalog_rows: list[dict[str, Any]] = []
    blockers = {
        BANK_EVIDENCE_NOT_POINT_IN_TIME,
        PILLAR3_DASFN_HISTORICAL_VINTAGE_QUERY_UNPROVEN,
        PILLAR3_DASFN_PAYLOAD_PUBLICATION_TIMESTAMP_UNPROVEN,
        PILLAR3_DASFN_REVISION_HISTORY_UNPROVEN,
        PILLAR3_DASFN_STRUCTURED_COVERAGE_GAP,
    }

    all_pages_trusted = True
    all_pages_parseable = True
    all_pages_contract_usable = True
    for page in normalized:
        page_evidence, rows = _page_evidence(page)
        evidence.append(page_evidence)
        if not page_evidence.trusted_http_success:
            all_pages_trusted = False
            blockers.add(PILLAR3_DASFN_CATALOG_PAGE_UNAVAILABLE)
            if _http_success(page) and not _final_url_trusted(page):
                blockers.add(PILLAR3_DASFN_SNAPSHOT_FINAL_URL_UNTRUSTED)
        if rows is None:
            all_pages_parseable = False
            all_pages_contract_usable = False
            blockers.add(PILLAR3_DASFN_CATALOG_SNAPSHOT_CONTRACT_UNUSABLE)
        else:
            catalog_rows.extend(rows)
            if not page_evidence.central_contract_usable:
                all_pages_contract_usable = False
                blockers.add(PILLAR3_DASFN_CATALOG_SNAPSHOT_CONTRACT_UNUSABLE)

    snapshot_complete = _snapshot_complete(normalized, evidence)
    if not snapshot_complete:
        blockers.add(PILLAR3_DASFN_CATALOG_SNAPSHOT_INCOMPLETE)

    pillar3_rows, local_filter_usable = _local_pillar3_rows(catalog_rows)
    if not pillar3_rows:
        blockers.add(PILLAR3_DASFN_LOCAL_FILTER_NO_ROWS)
    if not local_filter_usable:
        blockers.add(PILLAR3_DASFN_LOCAL_FILTER_ROW_UNUSABLE)

    central_contract_usable = bool(all_pages_parseable and all_pages_contract_usable)
    current_catalog_discovery_ready = bool(
        all_pages_trusted
        and central_contract_usable
        and snapshot_complete
        and local_filter_usable
        and pillar3_rows
    )

    versions = tuple(sorted({row.versao for row in pillar3_rows}))
    version_families = tuple(sorted({_version_family(item) for item in versions}))
    resources = tuple(sorted({row.recurso for row in pillar3_rows}))
    institutions = tuple(sorted({row.cnpj_instituicao for row in pillar3_rows}))

    return BCBPillar3DASFNCatalogSnapshotAudit(
        collected_at=collected_at,
        catalog_source_url=catalog_source_url,
        pages=tuple(evidence),
        total_catalog_rows=len(catalog_rows),
        pillar3_rows=pillar3_rows,
        observed_version_families=version_families,
        observed_versions=versions,
        observed_resources=resources,
        observed_institutions=institutions,
        snapshot_complete=snapshot_complete,
        central_contract_usable=central_contract_usable,
        local_filter_usable=local_filter_usable,
        current_catalog_discovery_ready=current_catalog_discovery_ready,
        historical_vintage_query_proven=False,
        historical_replay_ready=False,
        bank_evidence_point_in_time_ready=False,
        readiness_promotion_allowed=False,
        blockers=tuple(sorted(blockers)),
    )


def _validate_page_sequence(pages: tuple[Pillar3DASFNCatalogPageInput, ...]) -> None:
    expected_skip = 0
    top = pages[0].top
    if top <= 0:
        raise ValueError("catalog page top must be positive")
    for page in pages:
        if page.top != top:
            raise ValueError("all catalog pages must use the same top")
        if page.skip != expected_skip:
            raise ValueError("catalog pages must be contiguous from skip=0")
        _validate_requested_page_url(page)
        expected_skip += top


def _validate_requested_page_url(page: Pillar3DASFNCatalogPageInput) -> None:
    parsed = urlparse(page.requested_url)
    endpoint = urlparse(_DASFN_CATALOG_ENDPOINT)
    if (parsed.scheme, parsed.netloc, parsed.path) != (
        endpoint.scheme,
        endpoint.netloc,
        endpoint.path,
    ):
        raise ValueError("catalog page URL must target the official DASFN Recursos endpoint")
    query = parse_qs(parsed.query, keep_blank_values=True)
    if "$filter" in query:
        raise ValueError("unfiltered catalog snapshot pages must not use $filter")
    allowed = {"$format", "$select", "$top", "$skip"}
    if set(query) - allowed:
        raise ValueError("catalog page URL contains unsupported query parameters")
    if query.get("$format") != ["json"]:
        raise ValueError("catalog page URL must request $format=json")
    if query.get("$select") != [_CENTRAL_SELECT]:
        raise ValueError("catalog page URL must select the bounded central fields")
    if query.get("$top") != [str(page.top)]:
        raise ValueError("catalog page URL $top does not match page metadata")
    if query.get("$skip") != [str(page.skip)]:
        raise ValueError("catalog page URL $skip does not match page metadata")


def _page_evidence(
    page: Pillar3DASFNCatalogPageInput,
) -> tuple[Pillar3DASFNCatalogPageEvidence, tuple[dict[str, Any], ...] | None]:
    if page.status_code is None:
        if page.transport_error is None:
            raise ValueError("page without HTTP status must preserve transport_error")
        if page.content is not None:
            raise ValueError("transport-error page must not contain response content")
        return (
            Pillar3DASFNCatalogPageEvidence(
                skip=page.skip,
                top=page.top,
                requested_url=page.requested_url,
                final_url=page.final_url,
                status_code=None,
                content_type=page.content_type,
                sha256=None,
                size_bytes=0,
                row_count=None,
                transport_error=page.transport_error,
                trusted_http_success=False,
                central_contract_usable=False,
            ),
            None,
        )

    if not (100 <= page.status_code <= 599):
        raise ValueError("HTTP status code must be between 100 and 599")
    if page.transport_error is not None:
        raise ValueError("HTTP response page must not contain transport_error")

    content = page.content or b""
    trusted = _trusted_http_success(page)
    rows = _try_catalog_rows(content) if trusted else None
    central_contract_usable = bool(
        rows is not None and _all_rows_match_central_contract(rows)
    )
    return (
        Pillar3DASFNCatalogPageEvidence(
            skip=page.skip,
            top=page.top,
            requested_url=page.requested_url,
            final_url=page.final_url,
            status_code=page.status_code,
            content_type=page.content_type,
            sha256=hashlib.sha256(content).hexdigest(),
            size_bytes=len(content),
            row_count=None if rows is None else len(rows),
            transport_error=None,
            trusted_http_success=trusted,
            central_contract_usable=central_contract_usable,
        ),
        rows,
    )


def _snapshot_complete(
    pages: tuple[Pillar3DASFNCatalogPageInput, ...],
    evidence: list[Pillar3DASFNCatalogPageEvidence],
) -> bool:
    if any(not item.trusted_http_success or item.row_count is None for item in evidence):
        return False
    if any(item.row_count != item.top for item in evidence[:-1]):
        return False
    last = evidence[-1]
    return last.row_count is not None and last.row_count < pages[-1].top


def _all_rows_match_central_contract(rows: tuple[dict[str, Any], ...]) -> bool:
    for row in rows:
        values = {
            field: _value_case_insensitive(row, field)
            for field in _REQUIRED_CENTRAL_FIELDS
        }
        if any(value is None or not str(value).strip() for value in values.values()):
            return False
        cnpj = str(values["CnpjInstituicao"]).strip()
        if len(cnpj) != 14 or not cnpj.isdigit():
            return False
    return True


def _local_pillar3_rows(
    rows: list[dict[str, Any]],
) -> tuple[tuple[Pillar3DASFNCatalogRow, ...], bool]:
    selected: list[Pillar3DASFNCatalogRow] = []
    usable = True
    for row in rows:
        api = _value_case_insensitive(row, "Api")
        if api is None or str(api).strip().casefold() != "pilar3":
            continue
        values = {
            field: _value_case_insensitive(row, field)
            for field in _REQUIRED_CENTRAL_FIELDS
        }
        if any(value is None or not str(value).strip() for value in values.values()):
            usable = False
            continue
        version = str(values["Versao"]).strip()
        if _version_family(version) not in {"v1", "v2"}:
            usable = False
            continue
        cnpj = str(values["CnpjInstituicao"]).strip()
        if len(cnpj) != 14 or not cnpj.isdigit():
            usable = False
            continue
        selected.append(
            Pillar3DASFNCatalogRow(
                cnpj_instituicao=cnpj,
                api=str(values["Api"]).strip(),
                versao=version,
                recurso=str(values["Recurso"]).strip(),
                url_dados=str(values["URLDados"]).strip(),
            )
        )
    return (
        tuple(
            sorted(
                selected,
                key=lambda item: (
                    item.cnpj_instituicao,
                    item.versao,
                    item.recurso,
                    item.url_dados,
                ),
            )
        ),
        usable,
    )


def _try_catalog_rows(content: bytes) -> tuple[dict[str, Any], ...] | None:
    if not content:
        return None
    try:
        payload = json.loads(content)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict) or not isinstance(payload.get("value"), list):
        return None
    rows = payload["value"]
    if any(not isinstance(row, dict) for row in rows):
        return None
    return tuple(rows)


def _http_success(page: Pillar3DASFNCatalogPageInput) -> bool:
    return page.status_code is not None and 200 <= page.status_code < 300


def _final_url_trusted(page: Pillar3DASFNCatalogPageInput) -> bool:
    if page.final_url is None:
        return False
    parsed = urlparse(page.final_url)
    endpoint = urlparse(_DASFN_CATALOG_ENDPOINT)
    if (parsed.scheme, parsed.netloc, parsed.path) != (
        endpoint.scheme,
        endpoint.netloc,
        endpoint.path,
    ):
        return False
    query = parse_qs(parsed.query, keep_blank_values=True)
    allowed = {"$format", "$select", "$top", "$skip"}
    if "$filter" in query or set(query) - allowed:
        return False
    return bool(
        query.get("$format") == ["json"]
        and query.get("$select") == [_CENTRAL_SELECT]
        and query.get("$top") == [str(page.top)]
        and query.get("$skip") == [str(page.skip)]
    )


def _trusted_http_success(page: Pillar3DASFNCatalogPageInput) -> bool:
    return _http_success(page) and _final_url_trusted(page)


def _version_family(version: str) -> str:
    if version == "1" or version.startswith("1."):
        return "v1"
    if version == "2" or version.startswith("2."):
        return "v2"
    return "unknown"


def _value_case_insensitive(row: dict[str, Any], field: str) -> Any:
    expected = field.casefold()
    for key, value in row.items():
        if str(key).casefold() == expected:
            return value
    return None
