from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, date, datetime
from pathlib import Path

import yaml

from ultimate_stock_analyzer.backtesting.bank_pit_source_routing import (
    BANK_CREDIT_LOSS_PIT_SOURCE_UNRESOLVED,
    BANK_EVIDENCE_NOT_POINT_IN_TIME,
    BANK_GROSS_CREDIT_PIT_SOURCE_UNRESOLVED,
    BANK_MODEL_PIT_COVERAGE_INCOMPLETE,
    BANK_NET_INCOME_GROWTH_PIT_WINDOW_UNPROVEN,
    BANK_SCOPE_ALIGNMENT_UNPROVEN,
    CVM_DFP_REVISION_HISTORY_COMPLETENESS_UNPROVEN,
    PILLAR3_IPE_REVISION_HISTORY_COMPLETENESS_UNPROVEN,
    CVMBankAccountingPeriodEvidence,
    audit_bank_pit_source_routing,
)
from ultimate_stock_analyzer.collectors.cvm import CVMCollector
from ultimate_stock_analyzer.fundamentals.cvm_accounts import extract_fixed_accounts
from ultimate_stock_analyzer.normalization.cvm import point_in_time_lines
from ultimate_stock_analyzer.orchestration.cvm_ingestion import CVMIngestionService


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Audit hybrid point-in-time source routes for the bank structural model."
    )
    parser.add_argument("--cvm-code", type=int, default=19348)
    parser.add_argument("--year", type=int, action="append", required=True)
    parser.add_argument(
        "--bank-config",
        default="config/scoring/sectors/banks_v0.6.yml",
    )
    parser.add_argument("--output", default="bank-pit-source-routing-audit.json")
    return parser


def main() -> None:
    args = _parser().parse_args()
    years = tuple(sorted(set(args.year)))
    if len(years) != len(args.year):
        raise SystemExit("years must not contain duplicates")
    if len(years) != 2 or years[1] != years[0] + 1:
        raise SystemExit("exactly two consecutive fiscal years are required")

    generated_at = datetime.now(UTC)
    collector = CVMCollector(timeout_seconds=180.0)
    service = CVMIngestionService(collector)
    periods = []
    archives = []

    for year in years:
        archive = collector.download_zip("DFP", year)
        archives.append(
            {
                "year": year,
                "source_url": collector.dataset_url("DFP", year),
                "sha256": hashlib.sha256(archive).hexdigest(),
                "size_bytes": len(archive),
            }
        )
        lines = service.load_statements_from_archive(
            archive,
            document_type="DFP",
            statements=("BPA", "BPP", "DRE"),
            scope_token="con",
            collected_at=generated_at,
        )
        reference_date = date(year, 12, 31)
        issuer_lines = [
            line
            for line in lines
            if line.cvm_code == args.cvm_code and line.reference_date == reference_date
        ]
        latest = point_in_time_lines(issuer_lines, as_of=generated_at)
        extraction = extract_fixed_accounts(
            latest,
            company_id=f"cvm:{args.cvm_code}",
            reference_date=reference_date,
            consolidation_scope=None,
        )
        required = ("total_assets", "equity", "net_income_consolidated")
        missing = [name for name in required if name not in extraction.values]
        if missing:
            raise RuntimeError(f"missing CVM bank accounting candidates for {year}: {missing}")
        selected = {name: extraction.lines[name] for name in required}
        untimed = [name for name, line in selected.items() if line.available_from is None]
        if untimed:
            raise RuntimeError(f"untimed CVM bank accounting candidates for {year}: {untimed}")
        periods.append(
            CVMBankAccountingPeriodEvidence(
                fiscal_year=year,
                total_assets=extraction.values["total_assets"],
                equity=extraction.values["equity"],
                net_income_consolidated=extraction.values["net_income_consolidated"],
                total_assets_available_from=(
                    selected["total_assets"].available_from.isoformat()
                ),
                equity_available_from=selected["equity"].available_from.isoformat(),
                net_income_available_from=(
                    selected["net_income_consolidated"].available_from.isoformat()
                ),
                source_documents=tuple(
                    sorted(
                        {
                            line.source_document
                            for line in selected.values()
                            if line.source_document
                        }
                    )
                ),
            )
        )

    audit = audit_bank_pit_source_routing(cvm_accounting_periods=tuple(periods))
    _validate_model_config(Path(args.bank_config), audit.model_metric_routes)
    report = audit.to_dict()
    report["company_id"] = f"cvm:{args.cvm_code}"
    report["generated_at"] = generated_at.isoformat()
    report["audited_year_pair"] = list(years)
    report["dfp_archives"] = archives
    report["warnings"] = [
        "CVM_DFP_ACCOUNTING_VALUES_ARE_TIMESTAMPED_CANDIDATES_NOT_PRUDENTIAL_EQUIVALENTS",
        "CVM_DFP_ARCHIVE_REVISION_HISTORY_COMPLETENESS_IS_NOT_PROVEN",
        "FIVE_YEAR_NET_INCOME_GROWTH_IS_NOT_COUNTED_WITH_ONLY_TWO_YEARS",
        "ONLY_PILLAR3_KM1_CAPITAL_RATIOS_ARE_VALIDATED_OBSERVED_PIT_BANK_INPUTS",
        "NO_BANK_READINESS_CHANGE_IN_THIS_BLOCK",
    ]

    required_blockers = {
        BANK_EVIDENCE_NOT_POINT_IN_TIME,
        BANK_SCOPE_ALIGNMENT_UNPROVEN,
        BANK_GROSS_CREDIT_PIT_SOURCE_UNRESOLVED,
        BANK_CREDIT_LOSS_PIT_SOURCE_UNRESOLVED,
        BANK_NET_INCOME_GROWTH_PIT_WINDOW_UNPROVEN,
        BANK_MODEL_PIT_COVERAGE_INCOMPLETE,
        CVM_DFP_REVISION_HISTORY_COMPLETENESS_UNPROVEN,
        PILLAR3_IPE_REVISION_HISTORY_COMPLETENESS_UNPROVEN,
    }
    if not required_blockers.issubset(report["blockers"]):
        raise RuntimeError("required bank fail-closed blockers disappeared")
    if report["proven_pit_critical_coverage"] != 0.2:
        raise RuntimeError("unexpected proven bank critical PIT coverage")
    if report["timestamped_candidate_or_better_critical_coverage"] != 0.7:
        raise RuntimeError("unexpected timestamped bank candidate coverage")
    if abs(report["proven_pit_model_weight"] - 0.16) > 1e-12:
        raise RuntimeError("unexpected proven bank model PIT weight")
    if abs(report["timestamped_candidate_or_better_model_weight"] - 0.375) > 1e-12:
        raise RuntimeError("unexpected timestamped bank candidate model weight")
    if report["bank_evidence_point_in_time_ready"] or report["readiness_promotion_allowed"]:
        raise RuntimeError("source routing audit must not promote bank readiness")

    Path(args.output).write_text(
        json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True),
        encoding="utf-8",
    )
    print(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True))


def _validate_model_config(config_path: Path, routes) -> None:
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    category_weights = raw["category_weights"]
    configured = {
        item["name"]: float(category_weights[item["category"]]) * float(item["weight"])
        for item in raw["metrics"]
    }
    routed = {item.metric: item.model_weight for item in routes}
    if configured.keys() != routed.keys():
        raise RuntimeError(
            "bank metric routing drift: "
            f"configured={sorted(configured)} routed={sorted(routed)}"
        )
    mismatched = {
        name: (configured[name], routed[name])
        for name in configured
        if abs(configured[name] - routed[name]) > 1e-12
    }
    if mismatched:
        raise RuntimeError(f"bank metric weight routing drift: {mismatched}")


if __name__ == "__main__":
    main()
