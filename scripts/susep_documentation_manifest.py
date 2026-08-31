from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from ultimate_stock_analyzer.collectors.susep_ses import SusepSesCollector


def run(output: Path) -> dict[str, object]:
    collector = SusepSesCollector()
    documentation = collector.download_table_documentation_bytes()
    manifest = collector.documentation_field_manifest(documentation)
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
            "Inspect exact SUSEP SES table-documentation field tokens without "
            "persisting the raw RTF."
        )
    )
    parser.add_argument(
        "--output",
        default="./susep-schema-artifacts/documentation_manifest.json",
    )
    args = parser.parse_args()
    manifest = run(Path(args.output))
    print(json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False))


if __name__ == "__main__":
    main()
