from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from ultimate_stock_analyzer.collectors.b3_classification import (
    B3_CLASSIFICATION_APP_URL,
    B3IndustryClassificationCollector,
)
from ultimate_stock_analyzer.collectors.cvm import CVMCollector
from ultimate_stock_analyzer.collectors.cvm_foreign import CVMForeignIssuerCollector
from ultimate_stock_analyzer.collectors.cvm_targeted_statements import (
    load_company_statements_from_archive,
)
from ultimate_stock_analyzer.orchestration.cvm_ingestion import CVMIngestionService
from ultimate_stock_analyzer.scoring.fige_metric_selection import (
    FigeMetricSelectionContract,
)
from ultimate_stock_analyzer.scoring.fige_peer_discovery import (
    discover_fige_classification_candidates,
    evaluate_fige_peer_discovery,
    schema_audit_company_ids,
)
from ultimate_stock_analyzer.scoring.sector_models import SectorModelRegistry
from ultimate_stock_analyzer.scoring.statement_tree_audit import (
    audit_financial_statement_tree,
)
from ultimate_stock_analyzer.universe.b3_partition import (
    partition_current_b3_classifications,
)
from ultimate_stock_analyzer.universe.eligibility import (
    classify_brazilian_equity_issuers,
)

DEFAULT_REGISTRY = "config/scoring/sector_registry_v0.6.yml"
DEFAULT_METRIC_CONTRACT = (
    "config/scoring/fige_financial_non_prudential_metric_contract_v0.1.yml"
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Discover FIGE non-prudential financial peer candidates without scoring "
            "or routing changes."
        )
    )
    parser.add_argument("--year", type=int, default=2025)
    parser.add_argument("--registry", default=DEFAULT_REGISTRY)
    parser.add_argument("--metric-contract", default=DEFAULT_METRIC_CONTRACT)
    parser.add_argument("--output", default="fige-peer-discovery-audit.json")
    args = parser.parse_args()

    collected_at = datetime.now(UTC)
    b3 = B3IndustryClassificationCollector()
    workbook = b3.download_workbook()
    company_catalog = b3.download_company_catalog_archive()
    classifications = b3.normalize(
        workbook,
        company_catalog,
        collected_at=collected_at,
    )

    domestic_issuers = CVMIngestionService().load_issuer_master(
        collected_at=collected_at,
        active_only=False,
    )
    foreign_issuers = CVMForeignIssuerCollector().collect(
        collected_at=collected_at
    )
    eligibility = classify_brazilian_equity_issuers(
        (record.company_id for record in classifications),
        brazilian_public_company_ids=(
            issuer.company_id for issuer in domestic_issuers
        ),
        foreign_issuer_company_ids=(
            issuer.company_id for issuer in foreign_issuers
        ),
    )
    eligible_records, partition = partition_current_b3_classifications(
        classifications,
        eligibility_report=eligibility,
    )

    registry = SectorModelRegistry.from_yaml(args.registry)
    metric_contract = FigeMetricSelectionContract.from_yaml(args.metric_contract)
    anchor, candidates = discover_fige_classification_candidates(
        eligible_records,
        registry=registry,
    )

    cvm = CVMCollector()
    archive = cvm.download_zip("DFP", args.year)
    audit_ids = (anchor.company_id, *schema_audit_company_ids(candidates))
    records_by_id = {record.company_id: record for record in eligible_records}
    statement_reports = {}
    for company_id in audit_ids:
        record = records_by_id[company_id]
        lines = load_company_statements_from_archive(
            archive,
            cvm_code=record.cvm_code,
            document_type="DFP",
            statements=("BPA", "BPP", "DRE"),
            scope_token="ind",
            collected_at=collected_at,
            collector=cvm,
        )
        statement_reports[company_id] = audit_financial_statement_tree(
            lines,
            company_id=company_id,
            max_depth=4,
        )

    report = evaluate_fige_peer_discovery(
        anchor=anchor,
        candidates=candidates,
        statement_reports=statement_reports,
        min_comparable_peers_for_cross_sectional_score=(
            metric_contract.min_comparable_peers_for_cross_sectional_score
        ),
    )
    payload = {
        "generated_at": collected_at.isoformat(),
        "source": "B3_LISTED_COMPANIES+CVM_DFP_CIA_ABERTA",
        "source_url": B3_CLASSIFICATION_APP_URL,
        "fiscal_year": args.year,
        "metric_selection_contract_id": metric_contract.contract_id,
        "metric_selection_contract_version": metric_contract.version,
        "current_brazilian_equity_universe": partition.to_dict(),
        "peer_discovery": report.to_dict(),
        "notes": [
            "Current-state diagnostic only; not PIT-safe for historical backtests.",
            "Identity comes only from normalized official B3/CVM identities.",
            "Specialized model routes are excluded before FIGE schema matching.",
            "Primary schema matching requires exact CVM account code and label.",
            "Schema compatibility is not economic peer approval.",
            "No score, weight, routing or applicability-registry change occurs here.",
        ],
    }
    Path(args.output).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
