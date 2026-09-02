from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

import httpx

from ultimate_stock_analyzer.backtesting.bcb_ifdata_pit_source_audit import (
    BANK_EVIDENCE_NOT_POINT_IN_TIME,
    IFDATA_HISTORICAL_VINTAGE_QUERY_UNAVAILABLE,
    IFDATA_REVISION_HISTORY_UNAVAILABLE,
    audit_bcb_ifdata_pit_source,
)
from ultimate_stock_analyzer.collectors.bcb_ifdata import IFDATA_BASE_URL

BCB_IFDATA_DATASET_URL = (
    "https://dadosabertos.bcb.gov.br/dataset/"
    "ifdata---dados-selecionados-de-instituies-financeiras"
)
DEFAULT_PERIODS = (202412, 202506, 202512)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Audit whether the public BCB IFData OData contract supports "
            "revision-aware point-in-time replay for historical bank evidence."
        )
    )
    parser.add_argument("--periods", nargs="+", type=int, default=list(DEFAULT_PERIODS))
    parser.add_argument("--output", default="bcb-ifdata-pit-source-audit.json")
    return parser


def _get(
    client: httpx.Client,
    path: str,
    params: dict[str, object] | None = None,
) -> bytes:
    response = client.get(f"{IFDATA_BASE_URL}/{path}", params=params)
    response.raise_for_status()
    return response.content


def _sample_payloads(
    client: httpx.Client,
    periods: tuple[int, ...],
) -> tuple[tuple[int, str, bytes], ...]:
    samples: list[tuple[int, str, bytes]] = []
    for ano_mes in periods:
        cadastro = _get(
            client,
            "IfDataCadastro(AnoMes=@AnoMes)",
            {
                "@AnoMes": ano_mes,
                "$format": "json",
                "$top": 5,
            },
        )
        samples.append((ano_mes, "cadastro", cadastro))
        report = _get(
            client,
            (
                "IfDataValores("
                "AnoMes=@AnoMes,TipoInstituicao=@TipoInstituicao,Relatorio=@Relatorio)"
            ),
            {
                "@AnoMes": ano_mes,
                "@TipoInstituicao": 1,
                "@Relatorio": "'1'",
                "$format": "json",
                "$top": 5,
            },
        )
        samples.append((ano_mes, "report_1", report))
    return tuple(samples)


def main() -> None:
    args = _parser().parse_args()
    periods = tuple(dict.fromkeys(args.periods))
    collected_at = datetime.now(UTC)
    with httpx.Client(timeout=120.0, follow_redirects=True) as client:
        metadata = _get(client, "$metadata")
        samples = _sample_payloads(client, periods)

    audit = audit_bcb_ifdata_pit_source(
        metadata_content=metadata,
        sample_payloads=samples,
        requested_ano_mes=periods,
        collected_at=collected_at,
        source_dataset_url=BCB_IFDATA_DATASET_URL,
    )
    report = audit.to_dict()
    report["official_publication_policy"] = (
        "BCB publishes IFData quarterly reports 60 days after March, June and "
        "September reference dates and 90 days after December."
    )
    report["warnings"] = [
        "INITIAL_RELEASE_TIMING_IS_NOT_REVISION_HISTORY",
        "ANOMES_IS_A_REFERENCE_PERIOD_NOT_AN_AS_OF_VINTAGE_SELECTOR",
        "COLLECTION_TIME_CAN_START_FORWARD_SNAPSHOT_LINEAGE_ONLY",
        "NO_BANK_EVIDENCE_OR_READINESS_PROMOTION_IN_THIS_BLOCK",
    ]
    required = {
        BANK_EVIDENCE_NOT_POINT_IN_TIME,
        IFDATA_HISTORICAL_VINTAGE_QUERY_UNAVAILABLE,
        IFDATA_REVISION_HISTORY_UNAVAILABLE,
    }
    if not required.issubset(audit.blockers):
        raise RuntimeError("fail-closed IFData point-in-time blockers must remain")

    Path(args.output).write_text(
        json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True),
        encoding="utf-8",
    )
    print(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
