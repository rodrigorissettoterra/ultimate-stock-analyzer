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
from ultimate_stock_analyzer.scoring.applicability_review import (
    load_structural_applicability_reviews,
)
from ultimate_stock_analyzer.scoring.b100_accounting_lifecycle import (
    B100_CVM_CODE,
    audit_b100_accounting_lifecycle,
)
from ultimate_stock_analyzer.scoring.b100_structural_resolution import (
    evaluate_b100_general_corporate_resolution,
)
from ultimate_stock_analyzer.scoring.sector_models import SectorModelRegistry
from ultimate_stock_analyzer.universe.b3_partition import (
    partition_current_b3_classifications,
)
from ultimate_stock_analyzer.universe.eligibility import (
    classify_brazilian_equity_issuers,
)

DEFAULT_REGISTRY = "config/scoring/sector_registry_v0.6.yml"
DEFAULT_PRIOR_REVIEWS = "config/universe/b3_structural_applicability_reviews_v0.4.json"
DEFAULT_CURRENT_REVIEWS = "config/universe/b3_structural_applicability_reviews_v0.5.json"
BASE_STATEMENTS = ("BPA", "BPP", "DRE")
CASH_FLOW_STATEMENTS = ("DFC_MI", "DFC_MD")
LIFECYCLE_SNAPSHOTS = (("DFP", 2025), ("ITR", 2026))


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Validate resolution of B100 to the existing general_corporate structural "
            "model without introducing any routing change."
        )
    )
    parser.add_argument("--registry", default=DEFAULT_REGISTRY)
    parser.add_argument("--prior-reviews", default=DEFAULT_PRIOR_REVIEWS)
    parser.add_argument("--current-reviews", default=DEFAULT_CURRENT_REVIEWS)
    parser.add_argument(
        "--output",
        default="b100-general-corporate-resolution-regression.json",
    )
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
    foreign_issuers = CVMForeignIssuerCollector().collect(collected_at=collected_at)
    eligibility = classify_brazilian_equity_issuers(
        (record.company_id for record in classifications),
        brazilian_public_company_ids=(issuer.company_id for issuer in domestic_issuers),
        foreign_issuer_company_ids=(issuer.company_id for issuer in foreign_issuers),
    )
    eligible_records, partition = partition_current_b3_classifications(
        classifications,
        eligibility_report=eligibility,
    )

    lifecycle_inputs = _collect_consolidated_lifecycle(collected_at=collected_at)
    lifecycle = audit_b100_accounting_lifecycle(lifecycle_inputs)
    registry = SectorModelRegistry.from_yaml(args.registry)
    prior_reviews = load_structural_applicability_reviews(args.prior_reviews)
    current_reviews = load_structural_applicability_reviews(args.current_reviews)
    regression = evaluate_b100_general_corporate_resolution(
        eligible_records,
        registry=registry,
        prior_reviews=prior_reviews,
        current_reviews=current_reviews,
        lifecycle=lifecycle,
    )

    payload = {
        "generated_at": collected_at.isoformat(),
        "source": "B3_LISTED_COMPANIES+CVM_ISSUER_REGISTRIES+CVM_DFP+CVM_ITR",
        "source_url": B3_CLASSIFICATION_APP_URL,
        "point_in_time_eligible": False,
        "current_brazilian_equity_universe": partition.to_dict(),
        "lifecycle": lifecycle.to_dict(),
        "regression": regression.to_dict(),
        "notes": [
            "B100 remains on the existing general_corporate default route; this block removes only the diagnostic applicability-review flag.",
            "The full eligible B3 universe is checked and the applicability-registry transition must produce zero routing deltas.",
            "DFP 2025 consolidated and current ITR 2026 consolidated must retain complete general-corporate critical-account coverage.",
            "The same consolidated snapshots must not satisfy the complete ITSA holding critical schema.",
            "The default fixed-account extractor now prefers consolidated CVM statements when available and never mixes accounting scopes.",
            "Current B3 classification and current CVM archives are latest-state evidence, not revision-aware point-in-time history.",
            "No scoring formula, model config, peer group, threshold, weight, rankability rule, valuation or recommendation is changed.",
        ],
    }
    Path(args.output).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, default=str)
        + "\n",
        encoding="utf-8",
    )
    if not regression.resolution_passed:
        raise RuntimeError(
            "B100 general-corporate resolution regression failed: "
            + ", ".join(regression.failures)
        )


def _collect_consolidated_lifecycle(
    *,
    collected_at: datetime,
) -> dict[tuple[str, int, str], list]:
    collector = CVMCollector()
    snapshots: dict[tuple[str, int, str], list] = {}
    for document_type, fiscal_year in LIFECYCLE_SNAPSHOTS:
        archive = collector.download_zip(document_type, fiscal_year)
        filenames = collector.list_csv_files(archive)
        statements = _available_statements(
            filenames,
            document_type=document_type,
            fiscal_year=fiscal_year,
        )
        snapshots[(document_type, fiscal_year, "con")] = (
            load_company_statements_from_archive(
                archive,
                cvm_code=B100_CVM_CODE,
                document_type=document_type,
                statements=statements,
                scope_token="con",
                collected_at=collected_at,
                collector=collector,
            )
        )
    return snapshots


def _available_statements(
    filenames: list[str],
    *,
    document_type: str,
    fiscal_year: int,
) -> tuple[str, ...]:
    available: list[str] = []
    for statement in (*BASE_STATEMENTS, *CASH_FLOW_STATEMENTS):
        needle = f"_{statement.lower()}_con_"
        matches = [name for name in filenames if needle in name.lower()]
        if len(matches) > 1:
            raise RuntimeError(
                "ambiguous consolidated CVM file in B100 resolution regression: "
                f"document={document_type} year={fiscal_year} "
                f"statement={statement} matches={len(matches)}"
            )
        if matches:
            available.append(statement)
        elif statement in BASE_STATEMENTS:
            raise RuntimeError(
                "required consolidated CVM file missing in B100 resolution regression: "
                f"document={document_type} year={fiscal_year} statement={statement}"
            )
    return tuple(available)


if __name__ == "__main__":
    main()
