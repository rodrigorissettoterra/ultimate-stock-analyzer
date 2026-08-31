from __future__ import annotations

import argparse
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from pathlib import Path

import httpx

from ultimate_stock_analyzer.collectors.b3_classification import (
    B3IndustryClassificationCollector,
)
from ultimate_stock_analyzer.collectors.b3_company_detail import (
    B3ListedCompanyDetail,
    B3ListedCompanyDetailCollector,
)
from ultimate_stock_analyzer.collectors.b3_cotahist_securities import (
    B3CotahistSecurityObserver,
)
from ultimate_stock_analyzer.universe.b3_current_security_audit import (
    audit_b3_current_security_state,
)

REVIEW_COMPANY_IDS = (
    "cvm:9512",
    "cvm:27693",
    "cvm:27634",
    "cvm:8036",
    "cvm:19879",
    "cvm:18759",
    "cvm:6041",
    "cvm:7617",
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Audit current B3 listed-security evidence without changing eligibility."
    )
    parser.add_argument("--year", type=int, default=datetime.now(UTC).year)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--output", default="b3-current-security-audit.json")
    args = parser.parse_args()
    if args.workers < 1 or args.workers > 8:
        raise ValueError("workers must be between 1 and 8")

    collected_at = datetime.now(UTC)
    classification_collector = B3IndustryClassificationCollector()
    classifications = classification_collector.normalize(
        classification_collector.download_workbook(),
        classification_collector.download_company_catalog_archive(),
        collected_at=collected_at,
    )
    if len(classifications) < 300:
        raise RuntimeError(
            f"B3 classification control unexpectedly small: {len(classifications)}"
        )

    detail_collector = B3ListedCompanyDetailCollector()
    details: dict[str, B3ListedCompanyDetail] = {}
    errors: dict[str, str] = {}
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {
            executor.submit(
                detail_collector.fetch,
                record.cvm_code,
                collected_at=collected_at,
            ): record.company_id
            for record in classifications
        }
        for future in as_completed(futures):
            company_id = futures[future]
            try:
                details[company_id] = future.result()
            except (httpx.HTTPError, OSError, RuntimeError, TypeError, ValueError) as exc:
                errors[company_id] = f"{type(exc).__name__}: {exc}"

    if "cvm:9512" not in details:
        raise RuntimeError(
            "Petrobras B3 GetDetail positive control unavailable: "
            + errors.get("cvm:9512", "<no detail>")
        )

    exact_codes = {
        code
        for detail in details.values()
        for code in detail.all_security_codes
        if code.strip()
    }
    if not exact_codes:
        raise RuntimeError("B3 GetDetail produced no exact security codes")

    observations = B3CotahistSecurityObserver().fetch_year(
        args.year,
        tickers=exact_codes,
    )
    report = audit_b3_current_security_state(
        classifications,
        details,
        observations,
        detail_errors=errors,
    )
    evidence_by_company = {
        item.company_id: item for item in report.company_evidence
    }
    petr = evidence_by_company.get("cvm:9512")
    if petr is None or petr.status != "B3_SHARE_DATE_WITH_CURRENT_SPOT_TRADE":
        raise RuntimeError(
            "Petrobras current B3 share-trading control failed: "
            + (petr.status if petr else "<missing>")
        )

    payload = {
        "generated_at": collected_at.isoformat(),
        "year": args.year,
        "decision_effect": "diagnostic_only",
        "point_in_time_eligible": False,
        "source_contracts": [
            "B3_INDUSTRY_CLASSIFICATION",
            "B3_LISTED_COMPANIES_GET_DETAIL",
            "B3_COTAHIST",
        ],
        "classification_unmapped_issuer_codes": list(
            classification_collector.last_unmapped_issuer_codes
        ),
        "review_cases": {},
        "report": report.to_dict(),
        "notes": [
            "This artifact is diagnostic only and does not define final security eligibility.",
            "GetDetail is requested by exact codeCVM; classification identity remains canonical cvm:<CD_CVM>.",
            "COTAHIST evidence is assigned only to exact security codes returned by valid B3 GetDetail identities.",
            "dateQuotation is treated as B3 share-quotation evidence, not as a ticker-type inference rule.",
            "No suffix/prefix/name/fuzzy security inference is used.",
            "Current evidence is not point-in-time historical evidence.",
        ],
    }
    report_dict = report.to_dict()
    rows = {
        row["company_id"]: row
        for row in report_dict["company_evidence"]
    }
    payload["review_cases"] = {
        company_id: rows.get(company_id) for company_id in REVIEW_COMPANY_IDS
    }
    Path(args.output).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, default=str)
        + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
