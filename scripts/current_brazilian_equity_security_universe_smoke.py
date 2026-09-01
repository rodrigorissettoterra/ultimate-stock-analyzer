from __future__ import annotations

import argparse
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict
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
from ultimate_stock_analyzer.collectors.cvm_foreign import CVMForeignIssuerCollector
from ultimate_stock_analyzer.domain.master import SectorClassificationRecord
from ultimate_stock_analyzer.orchestration.cvm_ingestion import CVMIngestionService
from ultimate_stock_analyzer.universe.b3_current_security_audit import (
    audit_b3_current_security_state,
)
from ultimate_stock_analyzer.universe.current_equity_securities import (
    CurrentBrazilianEquityCompanyDecision,
    CurrentBrazilianEquitySecurityUniverseReport,
    classify_current_brazilian_equity_securities,
)
from ultimate_stock_analyzer.universe.eligibility import (
    classify_brazilian_equity_issuers,
)

REVIEW_COMPANY_IDS = (
    "cvm:9512",   # Petrobras positive control
    "cvm:27693",  # Brisanet
    "cvm:27634",  # B100
    "cvm:18759",  # BSCS
    "cvm:8036",   # Light Serviços
    "cvm:19879",  # Light S.A.
    "cvm:23523",  # Porto Sudeste / TPR
    "cvm:26700",  # Eurofarma
    "cvm:80152",  # PPLA foreign-unit control
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build the deterministic current Brazilian B3 core-equity universe."
    )
    parser.add_argument("--year", type=int, default=datetime.now(UTC).year)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument(
        "--output",
        default="current-brazilian-equity-security-universe.json",
    )
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

    details, detail_errors = _collect_details(
        classifications,
        collected_at=collected_at,
        workers=args.workers,
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
    security_audit = audit_b3_current_security_state(
        classifications,
        details,
        observations,
        detail_errors=detail_errors,
    )

    domestic_issuers = CVMIngestionService().load_issuer_master(
        collected_at=collected_at,
        active_only=False,
    )
    foreign_issuers = CVMForeignIssuerCollector().collect(
        collected_at=collected_at
    )
    issuer_eligibility = classify_brazilian_equity_issuers(
        (record.company_id for record in classifications),
        brazilian_public_company_ids=(
            issuer.company_id for issuer in domestic_issuers
        ),
        foreign_issuer_company_ids=(
            issuer.company_id for issuer in foreign_issuers
        ),
    )
    universe = classify_current_brazilian_equity_securities(
        issuer_eligibility=issuer_eligibility,
        security_audit=security_audit,
    )

    companies = {item.company_id: item for item in universe.company_decisions}
    _validate_controls(universe, companies)

    review_cases = {
        company_id: (asdict(companies[company_id]) if company_id in companies else None)
        for company_id in REVIEW_COMPANY_IDS
    }
    payload = {
        "generated_at": collected_at.isoformat(),
        "year": args.year,
        "scope": universe.scope,
        "point_in_time_eligible": False,
        "source_contracts": [
            "CVM_CAD",
            "CVM_FOREIGN_ISSUER_CAD",
            "B3_INDUSTRY_CLASSIFICATION",
            "B3_LISTED_COMPANIES_GET_DETAIL",
            "B3_COTAHIST",
            "B3_COTAHIST_ESPECI_TABLE",
        ],
        "classification_unmapped_issuer_codes": list(
            classification_collector.last_unmapped_issuer_codes
        ),
        "cotahist_latest_trade_date": (
            security_audit.cotahist_latest_trade_date.isoformat()
            if security_audit.cotahist_latest_trade_date
            else None
        ),
        "review_cases": review_cases,
        "universe": universe.to_dict(),
        "notes": [
            "company_id = cvm:<CD_CVM> remains the canonical issuer identity.",
            "Issuer jurisdiction is evaluated before any security can become eligible.",
            "Only exact codes returned by a valid B3 GetDetail identity are evaluated.",
            "An eligible security requires current-year B3 spot-market trade evidence and a coherent core-equity ESPECI kind.",
            "Core-equity kinds are COMMON_SHARE, PREFERRED_SHARE and UNIT.",
            "Receipts, bonuses, rights, BDR, TPR and other non-core kinds remain visible as explicit exclusions.",
            "Unknown or conflicting ESPECI values fail closed.",
            "dateQuotation is retained as corroborative B3 evidence but is not used to infer security type.",
            "This current-state contract is not point-in-time historical listing evidence.",
        ],
    }
    Path(args.output).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, default=str)
        + "\n",
        encoding="utf-8",
    )


def _collect_details(
    classifications: list[SectorClassificationRecord],
    *,
    collected_at: datetime,
    workers: int,
) -> tuple[dict[str, B3ListedCompanyDetail], dict[str, str]]:
    collector = B3ListedCompanyDetailCollector()
    details: dict[str, B3ListedCompanyDetail] = {}
    errors: dict[str, str] = {}
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(
                collector.fetch,
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
    return details, errors


def _validate_controls(
    universe: CurrentBrazilianEquitySecurityUniverseReport,
    companies: dict[str, CurrentBrazilianEquityCompanyDecision],
) -> None:
    if universe.eligible_company_count < 250:
        raise RuntimeError(
            "current Brazilian equity company universe unexpectedly small: "
            f"{universe.eligible_company_count}"
        )
    if universe.eligible_security_count < 300:
        raise RuntimeError(
            "current Brazilian equity security universe unexpectedly small: "
            f"{universe.eligible_security_count}"
        )
    if universe.security_status_counts.get("EXCLUDED_UNKNOWN_SECURITY_KIND", 0):
        raise RuntimeError("current security universe has unreviewed B3 ESPECI kinds")
    if universe.security_status_counts.get(
        "EXCLUDED_SECURITY_TAXONOMY_CONFLICT", 0
    ):
        raise RuntimeError("current security universe has B3 ESPECI taxonomy conflicts")

    petr = companies.get("cvm:9512")
    if petr is None or not petr.eligible:
        raise RuntimeError("Petrobras positive current-equity control failed")
    ppla = companies.get("cvm:80152")
    if ppla is None or ppla.status != "EXCLUDED_ISSUER_NOT_ELIGIBLE":
        raise RuntimeError("PPLA foreign-issuer control failed")
    bscs = companies.get("cvm:18759")
    if bscs is None or bscs.eligible:
        raise RuntimeError("BSCS non-equity current-universe control failed")


def _cnpj14(value: str | None) -> str | None:
    if value is None:
        return None
    digits = "".join(character for character in str(value) if character.isdigit())
    return digits.zfill(14) if digits else None


if __name__ == "__main__":
    main()
