from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath

from ultimate_stock_analyzer.collectors.susep_field_dictionary import (
    candidate_accounting_field_evidence,
    profitability_field_candidate_evidence,
    profitability_field_evidence,
)
from ultimate_stock_analyzer.collectors.susep_ses import SusepSesCollector


def run(output: Path) -> dict[str, object]:
    collector = SusepSesCollector()
    archive = collector.download_archive_bytes()
    manifest = collector.candidate_schema_manifest(archive)

    all_tables: dict[str, dict[str, object]] = {}
    for archive_path in collector.list_csv_files(archive):
        basename = PurePosixPath(archive_path).name
        all_tables[basename] = {
            "archive_path": archive_path,
            "columns": list(collector.inspect_schema(archive, basename)),
        }

    field_dictionary = collector.read_table(archive, "Ses_campos.csv")
    manifest["all_tables"] = all_tables
    manifest["accounting_field_candidates"] = candidate_accounting_field_evidence(
        field_dictionary
    )
    manifest["profitability_field_candidates"] = profitability_field_candidate_evidence(
        field_dictionary
    )
    manifest["profitability_field_evidence"] = profitability_field_evidence(
        field_dictionary
    )
    manifest["generated_at"] = datetime.now(UTC).isoformat()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Inspect official SUSEP SES schemas and selected field-dictionary evidence "
            "without persisting raw financial data."
        )
    )
    parser.add_argument("--output", default="./susep-schema-artifacts/schema_manifest.json")
    args = parser.parse_args()
    manifest = run(Path(args.output))
    print(json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False))


if __name__ == "__main__":
    main()
