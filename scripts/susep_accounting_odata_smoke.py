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

_SMOKE_YEAR = 2025
_SMOKE_RESOURCES = ("ContabeisDRE", "ContabeisAtivo")


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

    query_checks: list[dict[str, object]] = []
    for resource in _SMOKE_RESOURCES:
        rows = service.fetch_year_rows(resource, year=_SMOKE_YEAR, top=1)
        if not rows:
            raise RuntimeError(f"official SUSEP accounting resource returned no rows: {resource}")
        sample = rows[0]
        query_checks.append(
            {
                "resource": resource,
                "year": _SMOKE_YEAR,
                "row_count_requested": 1,
                "row_count_returned": len(rows),
                "sample_cmpid": sample.cmpid,
                "sample_cmp_title": sample.cmp_title,
                "parsed_cnpj_length": len(sample.cnpj),
            }
        )

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
        "live_year_query_checks": query_checks,
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
        "point_in_time_eligible": False,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Inspect the official SUSEP accounting OData service without storing financial rows."
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.output), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
