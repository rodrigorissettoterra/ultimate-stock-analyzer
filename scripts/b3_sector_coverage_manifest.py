from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from ultimate_stock_analyzer.collectors.b3_classification import (
    B3_CLASSIFICATION_APP_URL,
    B3IndustryClassificationCollector,
)
from ultimate_stock_analyzer.scoring.sector_coverage import profile_sector_model_coverage
from ultimate_stock_analyzer.scoring.sector_models import SectorModelRegistry


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
    report = profile_sector_model_coverage(
        normalized,
        registry=registry,
        classification_rows=len(workbook_rows),
        unmapped_issuer_codes=collector.last_unmapped_issuer_codes,
    )

    payload = {
        "generated_at": collected_at.isoformat(),
        "source": "B3_LISTED_COMPANIES",
        "source_url": B3_CLASSIFICATION_APP_URL,
        "registry_version": registry.version,
        "point_in_time_eligible": False,
        "report": report.to_dict(),
        "notes": [
            "Artifact contains aggregates and bounded public issuer identifiers only; no raw B3 workbook/catalog is persisted.",
            "general_corporate fallback is a valid model assignment, not by itself a data-quality failure.",
            "ambiguous_specialized_matches flags rows matching more than one specialized model and requires rule review.",
        ],
    }
    Path(args.output).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
