from __future__ import annotations

import argparse
from datetime import UTC, datetime
from pathlib import Path

from ultimate_stock_analyzer.backtesting.cvm_fca_applicability_filing_ledger import (
    build_fca_applicability_filing_ledger,
)
from ultimate_stock_analyzer.backtesting.cvm_fca_historical_model_routes import (
    FCAHistoricalModelRouteMapping,
    materialize_fca_historical_model_routes,
)
from ultimate_stock_analyzer.collectors.cvm import CVMCollector
from ultimate_stock_analyzer.scoring.sector_models import SectorModelRegistry


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Materialize versioned historical model routes from exact CVM FCA filings."
    )
    parser.add_argument("--year", action="append", type=int, required=True)
    parser.add_argument("--cvm-code", action="append", type=int, required=True)
    parser.add_argument("--mapping", type=Path, required=True)
    parser.add_argument("--sector-registry", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    years = tuple(sorted(set(args.year)))
    cvm_codes = tuple(sorted(set(args.cvm_code)))
    generated_at = datetime.now(UTC)
    collector = CVMCollector()

    ledgers = []
    for year in years:
        source_url = collector.dataset_url("FCA", year)
        archive = collector.download_zip("FCA", year)
        ledgers.append(
            build_fca_applicability_filing_ledger(
                archive_content=archive,
                collected_at=generated_at,
                delivery_year=year,
                source_url=source_url,
                requested_cvm_codes=cvm_codes,
            )
        )

    mapping = FCAHistoricalModelRouteMapping.from_yaml(args.mapping)
    registry = SectorModelRegistry.from_yaml(args.sector_registry)
    result = materialize_fca_historical_model_routes(
        ledgers=ledgers,
        mapping=mapping,
        sector_registry=registry,
    )
    args.output.write_text(
        result.model_dump_json(indent=2),
        encoding="utf-8",
        newline="\n",
    )


if __name__ == "__main__":
    main()
