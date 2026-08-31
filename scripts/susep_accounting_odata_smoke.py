from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from ultimate_stock_analyzer.collectors.susep_accounting_odata import (
    SUSEP_ACCOUNTING_DOCUMENTATION_URL,
    SUSEP_ACCOUNTING_ODATA_ROOT,
    VERIFIED_ACCOUNTING_RESOURCES,
    SusepAccountingODataService,
)


def run(output: Path) -> dict[str, object]:
    service = SusepAccountingODataService()
    catalog = service.fetch_resource_catalog()
    resource_names = tuple(resource.name for resource in catalog)
    missing = sorted(set(VERIFIED_ACCOUNTING_RESOURCES) - set(resource_names))
    if missing:
        raise RuntimeError(
            "official SUSEP accounting OData service is missing verified resources: "
            + ", ".join(missing)
        )

    callables = service.fetch_callable_catalog()
    callable_manifest = [
        {
            "kind": item.kind,
            "name": item.name,
            "target": item.target,
            "parameters": [
                {
                    "name": parameter.name,
                    "type": parameter.type_name,
                    "nullable": parameter.nullable,
                }
                for parameter in item.parameters
            ],
            "return_type": item.return_type,
        }
        for item in callables
    ]

    manifest: dict[str, object] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "SUSEP_OLINDA_ACCOUNTING",
        "service_root": SUSEP_ACCOUNTING_ODATA_ROOT,
        "documentation_url": SUSEP_ACCOUNTING_DOCUMENTATION_URL,
        "resource_count": len(resource_names),
        "resources": [
            {"name": resource.name, "url": resource.url}
            for resource in catalog
        ],
        "verified_canonical_resources": list(VERIFIED_ACCOUNTING_RESOURCES),
        "verified_canonical_resources_present": True,
        "metadata_callables": callable_manifest,
        "documented_row_fields": [
            "entnome",
            "cnpj",
            "mesreferencia",
            "cmpid",
            "cmptitulo",
            "valor",
            "cmpnumero",
        ],
        "raw_financial_rows_persisted": False,
        "semantic_promotion": False,
        "live_query_shape_promoted": False,
        "point_in_time_eligible": False,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Inspect official SUSEP accounting OData metadata without storing financial rows."
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.output), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
