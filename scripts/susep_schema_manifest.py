from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from ultimate_stock_analyzer.collectors.susep_ses import SusepSesCollector


def run(output: Path) -> dict[str, object]:
    collector = SusepSesCollector()
    archive = collector.download_archive_bytes()
    manifest = collector.candidate_schema_manifest(archive)
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
        description="Inspect official SUSEP SES candidate table schemas without persisting raw data."
    )
    parser.add_argument("--output", default="./susep-schema-artifacts/schema_manifest.json")
    args = parser.parse_args()
    manifest = run(Path(args.output))
    print(json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False))


if __name__ == "__main__":
    main()
