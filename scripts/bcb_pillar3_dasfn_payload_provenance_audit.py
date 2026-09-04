from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse

import httpx

from ultimate_stock_analyzer.backtesting.bcb_pillar3_dasfn_catalog_snapshot_audit import (
    BCBPillar3DASFNCatalogSnapshotAudit,
    Pillar3DASFNCatalogPageInput,
    Pillar3DASFNCatalogRow,
    audit_bcb_pillar3_dasfn_catalog_snapshot,
)
from ultimate_stock_analyzer.backtesting.bcb_pillar3_dasfn_payload_provenance_audit import (
    Pillar3InstitutionPayloadProbeInput,
    Pillar3PayloadSampleKey,
    audit_bcb_pillar3_institution_payload_provenance,
)

DASFN_CATALOG_URL = (
    "https://olinda.bcb.gov.br/olinda/servico/"
    "DASFN/versao/v1/odata/Recursos"
)
CENTRAL_SELECT = "Api,Versao,CnpjInstituicao,Recurso,URLDados"
TARGET_HOSTS = {
    "00000000000191": "api.externo.bb.com.br",
    "60701190000104": "cda.cloud.itau.com.br",
    "60746948000112": "openapi.bradesco.com.br",
    "90400888000142": "cms.santander.com.br",
}
REFERENCE_YEARS = (2022, 2025)
_HEADER_NAMES = (
    "date",
    "last-modified",
    "etag",
    "content-length",
    "cache-control",
    "location",
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Audit bounded Pillar 3 KM1 institution payload provenance for a "
            "deterministic four-bank sample without promoting PIT readiness."
        )
    )
    parser.add_argument(
        "--output",
        default="bcb-pillar3-dasfn-payload-provenance-audit.json",
    )
    parser.add_argument("--catalog-top", type=int, default=500)
    parser.add_argument("--catalog-max-pages", type=int, default=100)
    parser.add_argument("--max-body-bytes", type=int, default=2_000_000)
    return parser


def _catalog_page(
    client: httpx.Client,
    *,
    skip: int,
    top: int,
) -> Pillar3DASFNCatalogPageInput:
    params: dict[str, str | int] = {
        "$format": "json",
        "$select": CENTRAL_SELECT,
        "$top": top,
        "$skip": skip,
    }
    request = client.build_request("GET", DASFN_CATALOG_URL, params=params)
    requested_url = str(request.url)
    try:
        response = client.send(request)
    except httpx.HTTPError as error:
        return Pillar3DASFNCatalogPageInput(
            skip=skip,
            top=top,
            requested_url=requested_url,
            final_url=None,
            status_code=None,
            content_type=None,
            content=None,
            transport_error=f"{type(error).__name__}: {error}",
        )
    return Pillar3DASFNCatalogPageInput(
        skip=skip,
        top=top,
        requested_url=requested_url,
        final_url=str(response.url),
        status_code=response.status_code,
        content_type=response.headers.get("content-type"),
        content=response.content,
    )


def _row_count(page: Pillar3DASFNCatalogPageInput) -> int | None:
    if page.status_code is None or not 200 <= page.status_code < 300 or not page.content:
        return None
    try:
        payload = json.loads(page.content)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    rows = payload.get("value") if isinstance(payload, dict) else None
    return len(rows) if isinstance(rows, list) else None


def _catalog_snapshot(
    client: httpx.Client,
    *,
    top: int,
    max_pages: int,
    collected_at: datetime,
) -> BCBPillar3DASFNCatalogSnapshotAudit:
    pages: list[Pillar3DASFNCatalogPageInput] = []
    for index in range(max_pages):
        page = _catalog_page(client, skip=index * top, top=top)
        pages.append(page)
        row_count = _row_count(page)
        if row_count is None or row_count < top:
            break
    return audit_bcb_pillar3_dasfn_catalog_snapshot(
        pages=pages,
        collected_at=collected_at,
        catalog_source_url=DASFN_CATALOG_URL,
    )


def _expected_samples() -> tuple[Pillar3PayloadSampleKey, ...]:
    return tuple(
        Pillar3PayloadSampleKey(cnpj, year)
        for cnpj in TARGET_HOSTS
        for year in REFERENCE_YEARS
    )


def _year_end_url(url: str, year: int) -> bool:
    return f"{year}-4" in url or f"{year}1231" in url


def _version_family(version: str) -> str:
    if version == "2" or version.startswith("2."):
        return "v2"
    if version == "1" or version.startswith("1."):
        return "v1"
    return "unknown"


def _select_row(
    rows: tuple[Pillar3DASFNCatalogRow, ...],
    *,
    cnpj: str,
    year: int,
) -> Pillar3DASFNCatalogRow | None:
    expected_host = TARGET_HOSTS[cnpj]
    candidates = [
        row
        for row in rows
        if row.cnpj_instituicao == cnpj
        and row.recurso.casefold().startswith("/km1")
        and _year_end_url(row.url_dados, year)
        and (urlparse(row.url_dados).hostname or "").casefold() == expected_host
    ]
    if not candidates:
        return None
    preferred_family = "v1" if year <= 2023 else "v2"
    return sorted(
        candidates,
        key=lambda row: (
            _version_family(row.versao) != preferred_family,
            row.recurso.casefold() not in {"/km1/{trimestre}", "/km1/v2/{trimestre}"},
            row.versao,
            row.url_dados,
        ),
    )[0]


def _payload_probe(
    client: httpx.Client,
    *,
    row: Pillar3DASFNCatalogRow,
    reference_year: int,
    max_body_bytes: int,
) -> Pillar3InstitutionPayloadProbeInput:
    requested_url = row.url_dados
    try:
        with client.stream("GET", requested_url) as response:
            headers = tuple(
                (name, response.headers[name])
                for name in _HEADER_NAMES
                if name in response.headers
            )
            chunks: list[bytes] = []
            captured = 0
            body_complete = True
            for chunk in response.iter_bytes():
                remaining = max_body_bytes - captured
                if remaining <= 0:
                    body_complete = False
                    break
                if len(chunk) > remaining:
                    chunks.append(chunk[:remaining])
                    captured += remaining
                    body_complete = False
                    break
                chunks.append(chunk)
                captured += len(chunk)
            return Pillar3InstitutionPayloadProbeInput(
                cnpj_instituicao=row.cnpj_instituicao,
                reference_year=reference_year,
                version=row.versao,
                resource=row.recurso,
                central_url_dados=row.url_dados,
                requested_url=requested_url,
                final_url=str(response.url),
                status_code=response.status_code,
                content_type=response.headers.get("content-type"),
                response_headers=headers,
                content=b"".join(chunks),
                body_complete=body_complete,
            )
    except httpx.HTTPError as error:
        return Pillar3InstitutionPayloadProbeInput(
            cnpj_instituicao=row.cnpj_instituicao,
            reference_year=reference_year,
            version=row.versao,
            resource=row.recurso,
            central_url_dados=row.url_dados,
            requested_url=requested_url,
            final_url=None,
            status_code=None,
            content_type=None,
            response_headers=(),
            content=None,
            body_complete=True,
            transport_error=f"{type(error).__name__}: {error}",
        )


def main() -> None:
    args = _parser().parse_args()
    if args.catalog_top <= 0 or args.catalog_max_pages <= 0:
        raise ValueError("catalog pagination bounds must be positive")
    if args.catalog_top * args.catalog_max_pages > 50_000:
        raise ValueError("catalog snapshot bound must not exceed 50,000 rows")
    if args.max_body_bytes <= 0 or args.max_body_bytes > 5_000_000:
        raise ValueError("max body bytes must be between 1 and 5,000,000")

    collected_at = datetime.now(UTC)
    expected = _expected_samples()
    probes: list[Pillar3InstitutionPayloadProbeInput] = []
    with httpx.Client(timeout=120.0, follow_redirects=True) as catalog_client:
        snapshot = _catalog_snapshot(
            catalog_client,
            top=args.catalog_top,
            max_pages=args.catalog_max_pages,
            collected_at=collected_at,
        )

    if snapshot.current_catalog_discovery_ready:
        # URLDados is third-party input. Never follow redirects automatically: a 3xx
        # is preserved as unavailable evidence instead of allowing SSRF through an
        # institution-controlled redirect target.
        with httpx.Client(timeout=120.0, follow_redirects=False) as payload_client:
            for sample in expected:
                row = _select_row(
                    snapshot.pillar3_rows,
                    cnpj=sample.cnpj_instituicao,
                    year=sample.reference_year,
                )
                if row is not None:
                    probes.append(
                        _payload_probe(
                            payload_client,
                            row=row,
                            reference_year=sample.reference_year,
                            max_body_bytes=args.max_body_bytes,
                        )
                    )

    audit = audit_bcb_pillar3_institution_payload_provenance(
        expected_samples=expected,
        probes=probes,
        collected_at=collected_at,
    )
    report = audit.to_dict()
    report["catalog_snapshot"] = {
        "snapshot_complete": snapshot.snapshot_complete,
        "current_catalog_discovery_ready": snapshot.current_catalog_discovery_ready,
        "total_catalog_rows": snapshot.total_catalog_rows,
        "pillar3_row_count": len(snapshot.pillar3_rows),
        "blockers": list(snapshot.blockers),
    }
    report["sample_policy"] = {
        "target_cnpjs": list(TARGET_HOSTS),
        "reference_years": list(REFERENCE_YEARS),
        "resource": "KM1 year-end quarter",
        "max_payload_body_bytes": args.max_body_bytes,
        "allowed_hosts": TARGET_HOSTS,
        "payload_redirects_followed": False,
    }
    report["warnings"] = [
        "CURRENT_PAYLOAD_REACHABILITY_IS_NOT_HISTORICAL_VINTAGE_PROOF",
        "HTTP_LAST_MODIFIED_IS_NOT_ACCEPTED_AS_PAYLOAD_PUBLICATION_TIME",
        "ETAG_IS_NOT_ACCEPTED_AS_REVISION_HISTORY",
        "TIMESTAMP_LIKE_URL_OR_JSON_FIELDS_ARE_OBSERVATIONS_NOT_PIT_PROOF",
        "INSTITUTION_CATALOG_DATAULTIMAATUALIZACAO_IS_NOT_PAYLOAD_PUBLICATION_TIME",
        "PAYLOAD_REDIRECTS_ARE_NOT_FOLLOWED",
        "NO_BANK_EVIDENCE_OR_READINESS_PROMOTION_IN_THIS_BLOCK",
    ]

    Path(args.output).write_text(
        json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True),
        encoding="utf-8",
    )
    print(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
