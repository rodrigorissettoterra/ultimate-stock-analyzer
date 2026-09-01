from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from ultimate_stock_analyzer.collectors.b3_classification import (
    B3_CLASSIFICATION_APP_URL,
    B3IndustryClassificationCollector,
)
from ultimate_stock_analyzer.collectors.cvm_foreign import CVMForeignIssuerCollector
from ultimate_stock_analyzer.orchestration.cvm_ingestion import CVMIngestionService
from ultimate_stock_analyzer.scoring.applicability_review import (
    load_structural_applicability_reviews,
)
from ultimate_stock_analyzer.scoring.fige_structural_abstention import (
    evaluate_fige_structural_abstention,
)
from ultimate_stock_analyzer.scoring.sector_models import SectorModelRegistry
from ultimate_stock_analyzer.universe.b3_partition import (
    partition_current_b3_classifications,
)
from ultimate_stock_analyzer.universe.eligibility import (
    classify_brazilian_equity_issuers,
)

DEFAULT_REGISTRY = "config/scoring/sector_registry_v0.6.yml"
DEFAULT_APPLICABILITY_REVIEWS = (
    "config/universe/b3_structural_applicability_reviews_v0.3.json"
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Validate explicit FIGE structural abstention against the live current "
            "Brazilian-company B3 classification universe."
        )
    )
    parser.add_argument("--registry", default=DEFAULT_REGISTRY)
    parser.add_argument(
        "--applicability-reviews",
        default=DEFAULT_APPLICABILITY_REVIEWS,
    )
    parser.add_argument(
        "--output",
        default="fige-structural-abstention-regression.json",
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
    applicability_reviews = load_structural_applicability_reviews(
        args.applicability_reviews
    )
    regression = evaluate_fige_structural_abstention(
        eligible_records,
        registry=registry,
        applicability_reviews=applicability_reviews,
    )
    payload = {
        "generated_at": collected_at.isoformat(),
        "source": "B3_LISTED_COMPANIES+CVM_ISSUER_REGISTRIES",
        "source_url": B3_CLASSIFICATION_APP_URL,
        "point_in_time_eligible": False,
        "current_brazilian_equity_universe": partition.to_dict(),
        "regression": regression.to_dict(),
        "notes": [
            "The pre-abstention routing baseline is reconstructed by removing only the new abstention definition from the same registry object.",
            "The live routing delta must contain exactly cvm:6041 and no other eligible company.",
            "The abstention config contains no scoring metrics, categories, directions, targets, tolerances, weights or thresholds.",
            "Corporate metric probe values are intentionally varied to prove they cannot affect the FIGE abstention result.",
            "A historical routing backtest is intentionally not executed because current B3 classification is not revision-aware PIT evidence.",
            "The primary AnalyzerService recommendation engine is not changed by this structural routing block.",
        ],
    }
    Path(args.output).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    if not regression.regression_passed:
        raise RuntimeError(
            "FIGE structural abstention regression failed: "
            + ", ".join(regression.failures)
        )


if __name__ == "__main__":
    main()
