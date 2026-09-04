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
            "Audit whether BCB DASFN Pillar 3 structured APIs expose enough "
            "revision-aware evidence for historical point-in-time bank replay."
        )
    )
    parser.add_argument(
        "--output",
        default="bcb-pillar3-dasfn-pit-source-audit.json",
    )
    parser.add_argument("--top", type=int, default=1000)
    return parser


def _catalog_payload(client: httpx.Client, top: int) -> bytes:
    response = client.get(
        DASFN_CATALOG_URL,
        params={
            "$filter": "Api eq 'pilar3'",
            "$format": "json",
            "$top": top,
        },
    )
    response.raise_for_status()
    return response.content


def main() -> None:
    args = _parser().parse_args()
    if args.top <= 0:
        raise ValueError("--top must be positive")

    collected_at = datetime.now(UTC)
    with httpx.Client(timeout=120.0, follow_redirects=True) as client:
        catalog_content = _catalog_payload(client, args.top)

    audit = audit_bcb_pillar3_dasfn_pit_source(
        catalog_content=catalog_content,
        collected_at=collected_at,
        catalog_source_url=DASFN_CATALOG_URL,
        v1_dataset_url=PILLAR3_V1_DATASET_URL,
        v2_dataset_url=PILLAR3_V2_DATASET_URL,
    )
    report = audit.to_dict()
    report["official_source_notes"] = [
        (
            "BCB Pillar 3 v1 covers structured reference dates through "
            "2023-06-30."
        ),
        (
            "BCB Pillar 3 v2 covers structured reference dates from "
            "2025-12-31."
        ),
        (
            "Reference dates between those boundaries were disclosed by "
            "institutions as PDF rather than through the structured API."
        ),
        (
            "BCB catalogs institution-provided open-data links daily; the "
            "institution remains the host/provider of the underlying payload."
        ),
    ]
    report["warnings"] = [
        "REFERENCE_DATE_SELECTOR_IS_NOT_A_HISTORICAL_VINTAGE_SELECTOR",
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
