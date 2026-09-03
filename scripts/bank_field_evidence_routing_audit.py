from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

from ultimate_stock_analyzer.backtesting.bank_field_evidence_routing import (
    route_bank_field_evidence,
)
from ultimate_stock_analyzer.collectors.bcb_ifdata import BCBIFDataCollector
from ultimate_stock_analyzer.collectors.cvm import CVMCollector
from ultimate_stock_analyzer.domain.master import IssuerRecord
from ultimate_stock_analyzer.orchestration.cvm_ingestion import CVMIngestionService


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Route bank contract fields across official IFData and CVM evidence "
            "without promoting historical PIT readiness."
        )
    )
    parser.add_argument("--cvm-code", type=int, default=19348)
    parser.add_argument("--cnpj", default="60.872.504/0001-23")
    parser.add_argument("--year", type=int, action="append", required=True)
    parser.add_argument(
        "--output",
        default="bank-field-evidence-routing-audit.json",
    )
    return parser


def main() -> None:
    args = _parser().parse_args()
    years = tuple(sorted(set(args.year)))
    if len(years) != len(args.year):
        raise SystemExit("years must not contain duplicates")

    generated_at = datetime.now(UTC)
    issuer = IssuerRecord(
        company_id=f"cvm:{args.cvm_code}",
        cvm_code=args.cvm_code,
        cnpj=args.cnpj,
        legal_name=f"CVM issuer {args.cvm_code}",
        collected_at=generated_at,
    )
    cvm_collector = CVMCollector(timeout_seconds=180.0)
    cvm_service = CVMIngestionService(cvm_collector)
    ifdata_collector = BCBIFDataCollector(timeout=240.0)

    reports: list[dict[str, object]] = []
    dfp_archives: list[dict[str, object]] = []
    ifdata_payloads: list[dict[str, object]] = []

    for year in years:
        archive = cvm_collector.download_zip("DFP", year)
        dfp_archives.append(
            {
                "year": year,
                "source_url": cvm_collector.dataset_url("DFP", year),
                "sha256": hashlib.sha256(archive).hexdigest(),
                "size_bytes": len(archive),
            }
        )
        cvm_lines = cvm_service.load_company_statements_from_archive(
            archive,
            cvm_code=args.cvm_code,
            document_type="DFP",
            statements=("DRE",),
            scope_token="con",
            collected_at=generated_at,
        )
        collection = ifdata_collector.collect_annual_bank_profiles(
            (issuer,),
            fiscal_year=year,
            collected_at=generated_at,
        )
        if len(collection.profiles) != 1:
            raise RuntimeError(
                f"expected one IFData prudential profile for {args.cvm_code}/{year}, "
                f"found {len(collection.profiles)}"
            )
        for payload in collection.raw_payloads:
            ifdata_payloads.append(
                {
                    "fiscal_year": year,
                    "ano_mes": payload.ano_mes,
                    "kind": payload.kind,
                    "report_number": payload.report_number,
                    "sha256": hashlib.sha256(payload.content).hexdigest(),
                    "size_bytes": len(payload.content),
                }
            )

        as_of = datetime(year + 1, 6, 30, 23, 59, 59, tzinfo=UTC)
        report = route_bank_field_evidence(
            collection.profiles[0],
            as_of=as_of,
            cvm_lines=cvm_lines,
        )
        if report.readiness_promotion_allowed:
            raise RuntimeError("diagnostic bank field routing must not promote readiness")
        reports.append(report.to_dict())

    output = {
        "schema_version": "0.1",
        "effect": "live_bank_field_evidence_routing_no_readiness_promotion",
        "generated_at": generated_at.isoformat(),
        "target": {
            "company_id": issuer.company_id,
            "cvm_code": issuer.cvm_code,
            "cnpj": issuer.cnpj,
        },
        "years": list(years),
        "reports": reports,
        "dfp_archives": dfp_archives,
        "ifdata_payloads": ifdata_payloads,
        "warnings": [
            "CVM_3_09_IS_ISSUER_CONSOLIDATED_NOT_PRUDENTIAL_CONGLOMERATE",
            "IFDATA_HISTORICAL_ROWS_REMAIN_LATEST_STATE_WITHOUT_REVISION_LEDGER",
            "PILLAR3_FIELD_ROUTING_EXISTS_BUT_IS_NOT_EXERCISED_BY_THIS_LIVE_SMOKE",
            "NO_BANK_POINT_IN_TIME_READINESS_PROMOTION_IN_THIS_BLOCK",
        ],
    }
    Path(args.output).write_text(
        json.dumps(output, indent=2, ensure_ascii=False, sort_keys=True),
        encoding="utf-8",
    )
    print(json.dumps(output, indent=2, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
