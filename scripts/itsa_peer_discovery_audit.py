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
from ultimate_stock_analyzer.scoring.itsa_peer_discovery import (
    discover_itsa_exact_segment_candidates,
    evaluate_itsa_peer_discovery,
)
from ultimate_stock_analyzer.scoring.sector_models import SectorModelRegistry
from ultimate_stock_analyzer.scoring.structural import StructuralScoringConfig
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


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Discover exact-segment ITSA holding peer candidates without scoring or "
            "routing changes."
        )
    )
    parser.add_argument("--year", type=int, default=2025)
    parser.add_argument("--registry", default=DEFAULT_REGISTRY)
    parser.add_argument("--output", default="itsa-peer-discovery-audit.json")
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
    anchor, candidates = discover_itsa_exact_segment_candidates(
        eligible_records,
        registry=registry,
    )
    anchor_selection = registry.select(
        {
            "sector": anchor.sector,
            "subsector": anchor.subsector,
            "segment": anchor.segment,
            "industry": None,
        }
    )
    selected_config = StructuralScoringConfig.from_yaml(anchor_selection.config_path)
    min_peer_count = selected_config.default_min_peer_count

    cvm = CVMCollector()
    archive = cvm.download_zip("DFP", args.year)
    records_by_id = {record.company_id: record for record in eligible_records}
    audit_ids = (anchor.company_id, *(candidate.company_id for candidate in candidates))
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
            max_depth=6,
        )

    report = evaluate_itsa_peer_discovery(
        anchor=anchor,
        candidates=candidates,
        statement_reports=statement_reports,
        min_comparable_peers_for_cross_sectional_score=min_peer_count,
    )
    payload = {
        "generated_at": collected_at.isoformat(),
        "source": "B3_LISTED_COMPANIES+CVM_DFP_CIA_ABERTA",
        "source_url": B3_CLASSIFICATION_APP_URL,
        "fiscal_year": args.year,
        "selected_structural_model_id": anchor_selection.model_id,
        "selected_structural_model_family": selected_config.model_family,
        "selected_structural_default_min_peer_count": min_peer_count,
        "current_brazilian_equity_universe": partition.to_dict(),
        "peer_discovery": report.to_dict(),
        "notes": [
            "Current-state diagnostic only; not PIT-safe for historical backtests.",
            "Identity comes only from normalized official B3/CVM identities.",
            "Candidate scope is the anchor's exact B3 sector/subsector/segment only.",
            "Current sector-model routing is metadata only and never removes an exact-segment candidate.",
            "Critical schema compatibility requires all five ITSA contract-critical concepts by exact CVM account code and label.",
            "Schema compatibility is only a gate for later multi-year economic validation; it is not peer approval.",
            "The current structural minimum is read from the model selected for ITSA rather than duplicated in this audit.",
            "No score, weight, routing, rankability or applicability-registry change occurs here.",
        ],
    }
    Path(args.output).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
