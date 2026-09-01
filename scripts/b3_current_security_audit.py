from __future__ import annotations

import argparse
import json
from collections import Counter
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
from ultimate_stock_analyzer.universe.b3_security_types import (
    B3SecurityKind,
    classify_b3_security_specifications,
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
    classifications = [
        record.model_copy(update={"cnpj": _cnpj14(record.cnpj)})
        for record in classifications
    ]
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

    report_dict = report.to_dict()
    rows = {
        row["company_id"]: row
        for row in report_dict["company_evidence"]
    }
    taxonomy = _taxonomy_profile(report.security_evidence)
    payload = {
        "generated_at": collected_at.isoformat(),
        "year": args.year,
        "decision_effect": "diagnostic_only",
        "point_in_time_eligible": False,
        "source_contracts": [
            "B3_INDUSTRY_CLASSIFICATION",
            "B3_LISTED_COMPANIES_GET_DETAIL",
            "B3_COTAHIST",
            "B3_COTAHIST_ESPECI_TABLE",
        ],
        "classification_unmapped_issuer_codes": list(
            classification_collector.last_unmapped_issuer_codes
        ),
        "review_cases": {
            company_id: rows.get(company_id) for company_id in REVIEW_COMPANY_IDS
        },
        "security_type_taxonomy": taxonomy,
        "report": report_dict,
        "notes": [
            "This artifact is diagnostic only and does not define final security eligibility.",
            "GetDetail is requested by exact codeCVM; classification identity remains canonical cvm:<CD_CVM>.",
            "CNPJ is normalized to a 14-digit validation representation only inside this audit.",
            "COTAHIST evidence is assigned only to exact security codes returned by valid B3 GetDetail identities.",
            "B3 ESPECI is classified by documented security semantics, never by ticker digits.",
            "Subscription receipts (for example PN REC), rights and bonuses are not promoted to the underlying share class.",
            "Unknown or conflicting ESPECI states fail closed as non-core in this diagnostic taxonomy.",
            "Current evidence is not point-in-time historical evidence.",
        ],
    }
    Path(args.output).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, default=str)
        + "\n",
        encoding="utf-8",
    )


def _taxonomy_profile(security_evidence: tuple[object, ...]) -> dict[str, object]:
    kind_counts: Counter[str] = Counter()
    core_company_ids: set[str] = set()
    non_core_company_ids: set[str] = set()
    conflicts: list[dict[str, object]] = []
    unknown: list[dict[str, object]] = []
    observed_codes = 0
    core_codes = 0

    for item in security_evidence:
        trade_days = int(getattr(item, "trade_days"))
        if trade_days <= 0:
            continue
        observed_codes += 1
        result = classify_b3_security_specifications(getattr(item, "specifications"))
        code = str(getattr(item, "code"))
        company_id = str(getattr(item, "company_id"))
        if result.conflict:
            conflicts.append({
                "company_id": company_id,
                "code": code,
                **result.to_dict(),
            })
            non_core_company_ids.add(company_id)
            continue
        kind = result.coherent_kind or B3SecurityKind.OTHER_UNKNOWN
        kind_counts[kind.value] += 1
        if result.core_equity_security:
            core_codes += 1
            core_company_ids.add(company_id)
        else:
            non_core_company_ids.add(company_id)
        if kind == B3SecurityKind.OTHER_UNKNOWN:
            unknown.append({
                "company_id": company_id,
                "code": code,
                **result.to_dict(),
            })

    return {
        "observed_exact_security_codes": observed_codes,
        "coherent_kind_counts": dict(sorted(kind_counts.items())),
        "core_equity_security_codes": core_codes,
        "companies_with_core_equity_trade": len(core_company_ids),
        "companies_with_any_non_core_trade": len(non_core_company_ids),
        "security_kind_conflict_count": len(conflicts),
        "security_kind_conflicts": conflicts[:20],
        "unknown_security_count": len(unknown),
        "unknown_security_samples": unknown[:20],
        "core_equity_kinds": [
            B3SecurityKind.COMMON_SHARE.value,
            B3SecurityKind.PREFERRED_SHARE.value,
            B3SecurityKind.UNIT.value,
        ],
        "effect": "diagnostic_only",
    }


def _cnpj14(value: str | None) -> str | None:
    if value is None:
        return None
    digits = "".join(character for character in str(value) if character.isdigit())
    return digits.zfill(14) if digits else None


if __name__ == "__main__":
    main()
