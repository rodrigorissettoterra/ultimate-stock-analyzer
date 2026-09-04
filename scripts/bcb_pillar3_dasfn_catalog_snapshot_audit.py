from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

import httpx

from ultimate_stock_analyzer.backtesting.bcb_pillar3_dasfn_catalog_snapshot_audit import (
    Pillar3DASFNCatalogPageInput,
    audit_bcb_pillar3_dasfn_catalog_snapshot,
)
from ultimate_stock_analyzer.backtesting.bcb_pillar3_dasfn_pit_source_audit import (
    BANK_EVIDENCE_NOT_POINT_IN_TIME,
    PILLAR3_DASFN_HISTORICAL_VINTAGE_QUERY_UNPROVEN,
    PILLAR3_DASFN_PAYLOAD_PUBLICATION_TIMESTAMP_UNPROVEN,
    PILLAR3_DASFN_REVISION_HISTORY_UNPROVEN,
    PILLAR3_DASFN_STRUCTURED_COVERAGE_GAP,
)

DASFN_CATALOG_URL = (
    "https://olinda.bcb.gov.br/olinda/servico/"
    "DASFN/versao/v1/odata/Recursos"
)
CENTRAL_SELECT = "Api,Versao,CnpjInstituicao,Recurso,URLDados"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Audit the BCB DASFN central catalog using bounded unfiltered pagination "
            "and local Pillar 3 selection."
        )
    )
    parser.add_argument(
        "--output",
        default="bcb-pillar3-dasfn-catalog-snapshot-audit.json",
    )
    parser.add_argument("--top", type=int, default=500)
    parser.add_argument("--max-pages", type=int, default=20)
    return parser


def _page(
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
    if page.status_code is None or not (200 <= page.status_code < 300) or not page.content:
        return None
    try:
        payload = json.loads(page.content)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    rows = payload.get("value") if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        return None
    return len(rows)


def main() -> None:
    args = _parser().parse_args()
    if args.top <= 0:
        raise ValueError("--top must be positive")
    if args.max_pages <= 0:
        raise ValueError("--max-pages must be positive")

    collected_at = datetime.now(UTC)
    pages: list[Pillar3DASFNCatalogPageInput] = []
    with httpx.Client(timeout=120.0, follow_redirects=True) as client:
        for index in range(args.max_pages):
            page = _page(client, skip=index * args.top, top=args.top)
            pages.append(page)
            row_count = _row_count(page)
            if row_count is None or row_count < args.top:
                break

    audit = audit_bcb_pillar3_dasfn_catalog_snapshot(
        pages=pages,
        collected_at=collected_at,
        catalog_source_url=DASFN_CATALOG_URL,
    )
    report = audit.to_dict()
    report["collection_bounds"] = {
        "top": args.top,
        "max_pages": args.max_pages,
        "max_rows": args.top * args.max_pages,
        "selected_fields": CENTRAL_SELECT.split(","),
        "server_side_filter_used": False,
    }
    report["warnings"] = [
        "CURRENT_CATALOG_DISCOVERY_IS_NOT_HISTORICAL_VINTAGE_EVIDENCE",
        "LOCAL_PILLAR3_FILTER_IS_NOT_A_PUBLICATION_OR_REVISION_LEDGER",
        "NO_BANK_EVIDENCE_OR_READINESS_PROMOTION_IN_THIS_BLOCK",
    ]

    required = {
        BANK_EVIDENCE_NOT_POINT_IN_TIME,
        PILLAR3_DASFN_HISTORICAL_VINTAGE_QUERY_UNPROVEN,
        PILLAR3_DASFN_PAYLOAD_PUBLICATION_TIMESTAMP_UNPROVEN,
        PILLAR3_DASFN_REVISION_HISTORY_UNPROVEN,
        PILLAR3_DASFN_STRUCTURED_COVERAGE_GAP,
    }
    if not required.issubset(audit.blockers):
        raise RuntimeError("fail-closed DASFN PIT blockers must remain")
    if audit.historical_vintage_query_proven:
        raise RuntimeError("snapshot audit cannot prove historical vintage semantics")
    if audit.historical_replay_ready:
        raise RuntimeError("snapshot audit cannot make historical replay ready")
    if audit.bank_evidence_point_in_time_ready:
        raise RuntimeError("snapshot audit cannot promote bank PIT evidence")
    if audit.readiness_promotion_allowed:
        raise RuntimeError("snapshot audit cannot promote readiness")

    Path(args.output).write_text(
        json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True),
        encoding="utf-8",
    )
    print(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
