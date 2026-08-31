from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from ultimate_stock_analyzer.collectors.susep_provisions_odata import (
    SUSEP_PROVISIONS_DOCUMENTATION_URL,
    SUSEP_PROVISIONS_ODATA_ROOT,
    SusepProvisionsODataService,
)


def run(output: Path) -> dict[str, object]:
    catalog = SusepProvisionsODataService().fetch_resource_catalog()
    manifest: dict[str, object] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "SUSEP_OLINDA_PROVISIONS",
        "service_root": SUSEP_PROVISIONS_ODATA_ROOT,
        "documentation_url": SUSEP_PROVISIONS_DOCUMENTATION_URL,
        "resource_count": len(catalog),
        "resources": [{"name": item.name, "url": item.url} for item in catalog],
        "documented_insurance_fields": [
            "entnome",
            "cnpj",
            "mesreferencia",
            "grupo",
            "ramo",
            "provisao",
            "valor",
        ],
        "raw_financial_rows_persisted": False,
        "technical_provisions_coverage_promoted": False,
        "point_in_time_eligible": False,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Inspect official SUSEP provisions OData resources without storing balances."
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.output), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
