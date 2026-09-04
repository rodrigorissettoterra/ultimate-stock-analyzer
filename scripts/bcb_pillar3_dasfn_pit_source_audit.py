from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

import httpx

from ultimate_stock_analyzer.backtesting.bcb_pillar3_dasfn_pit_source_audit import (
    BANK_EVIDENCE_NOT_POINT_IN_TIME,
    PILLAR3_DASFN_HISTORICAL_VINTAGE_QUERY_UNPROVEN,
    PILLAR3_DASFN_PAYLOAD_PUBLICATION_TIMESTAMP_UNPROVEN,
    PILLAR3_DASFN_REVISION_HISTORY_UNPROVEN,
    PILLAR3_DASFN_STRUCTURED_COVERAGE_GAP,
    Pillar3DASFNCatalogProbeInput,
    audit_bcb_pillar3_dasfn_pit_source,
)

DASFN_CATALOG_URL = (
    "https://olinda.bcb.gov.br/olinda/servico/"
    "DASFN/versao/v1/odata/Recursos"
)
PILLAR3_V1_DATASET_URL = "https://dadosabertos.bcb.gov.br/dataset/pilar3"
PILLAR3_V2_DATASET_URL = "https://dadosabertos.bcb.gov.br/dataset/pilar3-v2"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Audit the current BCB DASFN Pillar 3 catalog contract without "
            "confusing endpoint availability with PIT-readiness evidence."
        )
    )
    parser.add_argument(
        "--output",
        default="bcb-pillar3-dasfn-pit-source-audit.json",
    )
    parser.add_argument("--top", type=int, default=1000)
    return parser


def _probe(
    client: httpx.Client,
    *,
    name: str,
    params: dict[str, object],
) -> Pillar3DASFNCatalogProbeInput:
    request = client.build_request("GET", DASFN_CATALOG_URL, params=params)
    requested_url = str(request.url)
    try:
        response = client.send(request)
    except httpx.HTTPError as error:
        return Pillar3DASFNCatalogProbeInput(
            name=name,
            requested_url=requested_url,
            final_url=None,
            status_code=None,
            content_type=None,
            content=None,
            transport_error=f"{type(error).__name__}: {error}",
        )
    return Pillar3DASFNCatalogProbeInput(
        name=name,
        requested_url=requested_url,
        final_url=str(response.url),
        status_code=response.status_code,
        content_type=response.headers.get("content-type"),
        content=response.content,
    )


def main() -> None:
    args = _parser().parse_args()
    if args.top <= 0:
        raise ValueError("--top must be positive")

    collected_at = datetime.now(UTC)
    with httpx.Client(timeout=120.0, follow_redirects=True) as client:
        probes = (
            _probe(
                client,
                name="base",
                params={"$format": "json", "$top": 1},
            ),
            _probe(
                client,
                name="pillar3_query",
                params={
                    "$filter": "Api eq 'pilar3'",
                    "$format": "json",
                    "$top": args.top,
                },
            ),
        )

    audit = audit_bcb_pillar3_dasfn_pit_source(
        probes=probes,
        collected_at=collected_at,
        catalog_source_url=DASFN_CATALOG_URL,
        v1_dataset_url=PILLAR3_V1_DATASET_URL,
        v2_dataset_url=PILLAR3_V2_DATASET_URL,
    )
    report = audit.to_dict()
    report["official_source_notes"] = [
        "Pillar 3 v1 structured coverage ends at 2023-06-30.",
        "Pillar 3 v2 structured coverage starts at 2025-12-31.",
        (
            "Reference dates strictly between those boundaries were disclosed "
            "as institution-hosted PDF rather than through the structured API."
        ),
        (
            "The BCB catalog and institution-hosted payload are separate "
            "evidence layers; catalog observation time is not payload publication time."
        ),
    ]
    report["warnings"] = [
        "REFERENCE_DATE_SELECTOR_IS_NOT_A_HISTORICAL_VINTAGE_SELECTOR",
        "CATALOG_HTTP_FAILURE_IS_SOURCE_CONTRACT_EVIDENCE_NOT_PIT_EVIDENCE",
        "CATALOG_COLLECTION_TIME_IS_NOT_PAYLOAD_PUBLICATION_TIME",
        "INSTITUTION_PAYLOADS_ARE_NOT_SAMPLED_IN_THIS_SOURCE_CONTRACT_AUDIT",
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
        raise RuntimeError("fail-closed Pillar 3 DASFN blockers must remain")

    Path(args.output).write_text(
        json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True),
        encoding="utf-8",
    )
    print(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
