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
from ultimate_stock_analyzer.scoring.sector_coverage import profile_sector_model_coverage
from ultimate_stock_analyzer.scoring.sector_models import SectorModelRegistry
from ultimate_stock_analyzer.universe.b3_partition import (
    partition_current_b3_classifications,
)
from ultimate_stock_analyzer.universe.eligibility import (
    classify_brazilian_equity_issuers,
)

DEFAULT_EXCLUSIONS = "config/universe/b3_non_equity_issuer_exclusions_v0.1.json"
DEFAULT_APPLICABILITY_REVIEWS = (
    "config/universe/b3_structural_applicability_reviews_v0.4.json"
)


def _load_verified_non_equity_exclusions(path: str) -> tuple[str, tuple[str, ...]]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    version = str(payload.get("version") or "").strip()
    entries = payload.get("exclusions")
    if not version:
        raise ValueError("B3 non-equity exclusion registry has no version")
    if not isinstance(entries, list):
        raise TypeError("B3 non-equity exclusion registry has no exclusions list")

    codes: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            raise TypeError("B3 non-equity exclusion entry must be an object")
        code = str(entry.get("issuer_code") or "").strip().upper()
        evidence_urls = entry.get("evidence_urls")
        if not code:
            raise ValueError("B3 non-equity exclusion entry has no issuer_code")
        if not isinstance(evidence_urls, list) or not evidence_urls:
            raise ValueError(
                f"B3 non-equity exclusion has no evidence_urls: issuer_code={code}"
            )
        if code in codes:
            raise ValueError(f"Duplicate B3 non-equity exclusion: issuer_code={code}")
        codes.add(code)
    return version, tuple(sorted(codes))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate a sanitized B3 sector/model coverage manifest."
    )
    parser.add_argument(
        "--registry",
        default="config/scoring/sector_registry_v0.6.yml",
        help="Sector model registry YAML.",
    )
    parser.add_argument(
        "--non-equity-exclusions",
        default=DEFAULT_EXCLUSIONS,
        help="Audited B3 issuer exclusions JSON.",
    )
    parser.add_argument(
        "--applicability-reviews",
        default=DEFAULT_APPLICABILITY_REVIEWS,
        help="Diagnostic-only structural applicability review registry JSON.",
    )
    parser.add_argument(
        "--output",
        default="b3-sector-coverage.json",
        help="Sanitized JSON output path.",
    )
    args = parser.parse_args()

    collected_at = datetime.now(UTC)
    collector = B3IndustryClassificationCollector()
    workbook = collector.download_workbook()
    catalog = collector.download_company_catalog_archive()
    workbook_rows = collector.parse_workbook(workbook)
    normalized = collector.normalize(workbook, catalog, collected_at=collected_at)
    registry = SectorModelRegistry.from_yaml(args.registry)
    exclusions_version, verified_non_equity_codes = (
        _load_verified_non_equity_exclusions(args.non_equity_exclusions)
    )
    applicability_reviews = load_structural_applicability_reviews(
        args.applicability_reviews
    )

    raw_report = profile_sector_model_coverage(
        normalized,
        registry=registry,
        classification_rows=len(workbook_rows),
        outside_active_company_catalog_issuer_codes=(
            collector.last_unmapped_issuer_codes
        ),
        verified_non_equity_issuer_codes=verified_non_equity_codes,
        applicability_review_registry=applicability_reviews,
    )

    domestic_issuers = CVMIngestionService().load_issuer_master(
        collected_at=collected_at,
        active_only=False,
    )
    foreign_issuers = CVMForeignIssuerCollector().collect(
        collected_at=collected_at
    )
    eligibility = classify_brazilian_equity_issuers(
        (record.company_id for record in normalized),
        brazilian_public_company_ids=(
            issuer.company_id for issuer in domestic_issuers
        ),
        foreign_issuer_company_ids=(
            issuer.company_id for issuer in foreign_issuers
        ),
    )
    eligible_records, partition_report = partition_current_b3_classifications(
        normalized,
        eligibility_report=eligibility,
    )
    eligible_model_report = profile_sector_model_coverage(
        eligible_records,
        registry=registry,
        classification_rows=len(eligible_records),
    )

    payload = {
        "generated_at": collected_at.isoformat(),
        "source": "B3_LISTED_COMPANIES",
        "source_url": B3_CLASSIFICATION_APP_URL,
        "registry_version": registry.version,
        "non_equity_exclusions_version": exclusions_version,
        "structural_applicability_review_version": applicability_reviews.version,
        "jurisdiction_source_contracts": [
            "CVM_CAD",
            "CVM_FOREIGN_ISSUER_CAD",
        ],
        "point_in_time_eligible": False,
        "report": raw_report.to_dict(),
        "current_brazilian_equity_universe": partition_report.to_dict(),
        "eligible_brazilian_equity_model_coverage": eligible_model_report.to_dict(),
        "notes": [
            "Artifact contains aggregates and bounded public issuer identifiers only; no raw B3 workbook/catalog or CVM registry is persisted.",
            "The top-level report preserves the raw mapped B3 classification/model view for audit continuity.",
            "company_catalog_join_coverage measures official classification workbook rows that resolve to an active official company-catalog identity; it is not claimed as the full equity-universe denominator.",
            "equity_candidate_identity_coverage excludes only explicitly audited non-equity/non-exchange-equity issuer rows and still is not the jurisdiction-filtered Brazilian-company universe denominator.",
            "current_brazilian_equity_universe partitions mapped B3 canonical CVM identities by separate official CVM Brazilian-public-company and foreign-issuer registries.",
            "eligible_brazilian_equity_model_coverage profiles only current Brazilian-company-eligible classification records; foreign, conflicting and unresolved identities remain visible in the partition audit instead of being silently dropped.",
            "Unresolved outside-catalog rows remain visible and are never guessed into an issuer identity.",
            "general_corporate fallback is valid but its sector/subsector distribution is reported for economic-model review.",
            "Structural applicability review statuses are diagnostic_only and do not alter model routing, score, rankability, weights or thresholds.",
            "Current B3 sector and CVM jurisdiction registries are current-state evidence and are not point-in-time eligible for historical backtests.",
            "ambiguous_specialized_matches flags rows matching more than one specialized model and requires rule review.",
        ],
    }
    Path(args.output).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
