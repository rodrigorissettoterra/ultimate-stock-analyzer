from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from ultimate_stock_analyzer.collectors.susep_identity import SusepOlindaIdentityCollector


def run(output: Path) -> dict[str, object]:
    collector = SusepOlindaIdentityCollector()
    records = collector.fetch_records()
    cnpjs = {record.normalized_cnpj for record in records}
    fip_codes = {record.normalized_fip_code for record in records}
    manifest: dict[str, object] = {
        "source": "SUSEP_OLINDA_EMPRESAS",
        "source_url": collector.endpoint,
        "entity_count": len(records),
        "unique_cnpj_count": len(cnpjs),
        "unique_fip_code_count": len(fip_codes),
        "identity_fields": ["mercodigo", "entcodigofip", "entnome", "entcgc"],
        "matching_key": "exact_normalized_cnpj",
        "fuzzy_matching_allowed": False,
        "generated_at": datetime.now(UTC).isoformat(),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate SUSEP Olinda identity API and emit aggregate metadata only."
    )
    parser.add_argument("--output", default="./susep-identity-artifacts/identity_manifest.json")
    args = parser.parse_args()
    print(json.dumps(run(Path(args.output)), indent=2, sort_keys=True, ensure_ascii=False))


if __name__ == "__main__":
    main()
