from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath

import pandas as pd

from ultimate_stock_analyzer.collectors.susep_ses import SusepSesCollector

_ACCOUNTING_FIELD_CANDIDATES = (542, 4069)
_FIELD_DICTIONARY_COLUMNS = (
    "nuitem",
    "noitem",
    "nuquad",
    "mercado",
    "inivigencia",
    "fimvigencia",
)


def _candidate_accounting_field_evidence(table: pd.DataFrame) -> dict[str, object]:
    missing = [column for column in _FIELD_DICTIONARY_COLUMNS if column not in table.columns]
    if missing:
        raise ValueError(
            "missing required SUSEP Ses_campos columns: " + ", ".join(missing)
        )

    item_ids = pd.to_numeric(table["nuitem"], errors="coerce")
    evidence: dict[str, object] = {}
    for candidate in _ACCOUNTING_FIELD_CANDIDATES:
        selected = table.loc[item_ids == candidate, list(_FIELD_DICTIONARY_COLUMNS)].copy()
        rows: list[dict[str, object]] = []
        for _, row in selected.iterrows():
            rows.append(
                {
                    column: None if pd.isna(row[column]) else str(row[column]).strip()
                    for column in _FIELD_DICTIONARY_COLUMNS
                }
            )
        evidence[str(candidate)] = {
            "present": bool(rows),
            "rows": rows,
        }

    return {
        "source_table": "Ses_campos.csv",
        "candidate_ids": list(_ACCOUNTING_FIELD_CANDIDATES),
        "semantics_promoted": False,
        "fields": evidence,
    }


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

    manifest["all_tables"] = all_tables
    manifest["accounting_field_candidates"] = _candidate_accounting_field_evidence(
        collector.read_table(archive, "Ses_campos.csv")
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
