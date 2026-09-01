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
from ultimate_stock_analyzer.scoring.holding_segment_economic_stability import (
    HoldingSegmentMember,
    audit_holding_segment_economic_stability,
)
from ultimate_stock_analyzer.scoring.itsa_peer_discovery import (
    discover_itsa_exact_segment_candidates,
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


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Audit multi-year accounting and economic stability for ITSA's current "
            "exact B3 holding segment."
        )
    )
    parser.add_argument("--start-year", type=int, default=2021)
    parser.add_argument("--end-year", type=int, default=2025)
    parser.add_argument("--registry", default=DEFAULT_REGISTRY)
    parser.add_argument(
        "--output",
        default="holding-segment-economic-stability-audit.json",
    )
    args = parser.parse_args()
    if args.start_year > args.end_year:
        raise ValueError("start-year must not be greater than end-year")

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
    members = (
        HoldingSegmentMember(
            company_id=anchor.company_id,
            cvm_code=anchor.cvm_code,
            issuer_code=anchor.issuer_code,
            trading_name=anchor.trading_name,
            sector=anchor.sector,
            subsector=anchor.subsector,
            segment=anchor.segment,
            model_id=anchor.model_id,
        ),
        *(
            HoldingSegmentMember(
                company_id=candidate.company_id,
                cvm_code=candidate.cvm_code,
                issuer_code=candidate.issuer_code,
                trading_name=candidate.trading_name,
                sector=candidate.sector,
                subsector=candidate.subsector,
                segment=candidate.segment,
                model_id=candidate.model_id,
            )
            for candidate in candidates
        ),
    )

    cvm = CVMCollector()
    reports_by_company_year = {}
    for year in range(args.start_year, args.end_year + 1):
        archive = cvm.download_zip("DFP", year)
        for member in members:
            lines = load_company_statements_from_archive(
                archive,
                cvm_code=member.cvm_code,
                document_type="DFP",
                statements=("BPA", "BPP", "DRE"),
                scope_token="ind",
                collected_at=collected_at,
                collector=cvm,
            )
            reports_by_company_year[(member.company_id, year)] = (
                audit_financial_statement_tree(
                    lines,
                    company_id=member.company_id,
                    max_depth=6,
                )
            )

    report = audit_holding_segment_economic_stability(
        members=members,
        reports_by_company_year=reports_by_company_year,
        anchor_company_id=anchor.company_id,
        start_year=args.start_year,
        end_year=args.end_year,
    )
    payload = {
        "generated_at": collected_at.isoformat(),
        "source": "B3_LISTED_COMPANIES+CVM_DFP_CIA_ABERTA",
        "source_url": B3_CLASSIFICATION_APP_URL,
        "current_brazilian_equity_universe": partition.to_dict(),
        "audit": report.to_dict(),
        "notes": [
            "Diagnostic only: no holding-dominance threshold, score or routing rule is defined here.",
            "Current exact-segment membership comes from the official B3 snapshot and is not projected backward as historical classification.",
            "Annual DFP evidence is evaluated with the exact ITSA holding accounting bindings; missing years or codes remain UNKNOWN.",
            "Investment parent and child accounts are reported separately; investments/assets uses only parent code 1.02.02.",
            "Metric ranges summarize observed values only and do not classify a company as a holding or non-holding.",
            "Current B3 classification and latest-state CVM annual archives are not revision-aware point-in-time evidence for strict historical backtests.",
            "segment_routing_ready and applicability_registry_resolvable remain false regardless of the live descriptive results.",
        ],
    }
    Path(args.output).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
