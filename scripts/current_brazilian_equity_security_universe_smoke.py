from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from ultimate_stock_analyzer.collectors.b3_classification import (
    B3IndustryClassificationCollector,
)
from ultimate_stock_analyzer.collectors.cvm_foreign import CVMForeignIssuerCollector
from ultimate_stock_analyzer.orchestration.cvm_ingestion import CVMIngestionService
from ultimate_stock_analyzer.universe.eligibility import (
    classify_brazilian_equity_issuers,
)
from ultimate_stock_analyzer.universe.security_eligibility import (
    classify_current_brazilian_equity_securities,
)

SELECTED_COMPANY_IDS = (
    "cvm:6041",   # FIGE
    "cvm:18759",  # BSCS
    "cvm:27634",  # B100
    "cvm:7617",   # ITSA
    "cvm:9512",   # PETR
    "cvm:80195",  # G2DI foreign control
    "cvm:80152",  # PPLA foreign control
)


def main() -> None:
    collected_at = datetime.now(UTC)
    year = collected_at.year

    b3_collector = B3IndustryClassificationCollector()
    classifications = b3_collector.normalize(
        b3_collector.download_workbook(),
        b3_collector.download_company_catalog_archive(),
        collected_at=collected_at,
    )
    candidate_company_ids = tuple(record.company_id for record in classifications)
    classification_by_id = {record.company_id: record for record in classifications}

    cvm_service = CVMIngestionService()
    domestic_issuers = cvm_service.load_issuer_master(
        collected_at=collected_at,
        active_only=False,
    )
    foreign_issuers = CVMForeignIssuerCollector().collect(collected_at=collected_at)
    issuer_eligibility = classify_brazilian_equity_issuers(
        candidate_company_ids,
        brazilian_public_company_ids=(issuer.company_id for issuer in domestic_issuers),
        foreign_issuer_company_ids=(issuer.company_id for issuer in foreign_issuers),
    )
    securities = cvm_service.load_security_master(
        year=year,
        collected_at=collected_at,
    )
    eligible_securities, report = classify_current_brazilian_equity_securities(
        candidate_company_ids,
        securities,
        issuer_eligibility_report=issuer_eligibility,
        as_of=collected_at.date(),
    )

    company_by_id = {decision.company_id: decision for decision in report.company_decisions}

    def company_payload(company_id: str) -> dict[str, object]:
        decision = company_by_id[company_id]
        classification = classification_by_id.get(company_id)
        return {
            "company_id": company_id,
            "issuer_code": classification.issuer_code if classification else None,
            "trading_name": classification.trading_name if classification else None,
            "sector": classification.sector if classification else None,
            "subsector": classification.subsector if classification else None,
            "segment": classification.segment if classification else None,
            "status": decision.status,
            "eligible": decision.eligible,
            "eligible_tickers": list(decision.eligible_tickers),
            "reason": decision.reason,
        }

    selected_companies = [
        company_payload(company_id)
        for company_id in SELECTED_COMPANY_IDS
        if company_id in company_by_id
    ]
    excluded_companies = [
        company_payload(decision.company_id)
        for decision in report.company_decisions
        if not decision.eligible
    ]

    def security_payload(decision: object) -> dict[str, object]:
        return {
            "company_id": decision.company_id,
            "ticker": decision.ticker,
            "status": decision.status,
            "eligible": decision.eligible,
            "security_type": decision.security_type,
            "market": decision.market,
            "administrator": decision.administrator,
            "active_as_of": decision.active_as_of,
            "reason": decision.reason,
        }

    selected_security_decisions = [
        security_payload(decision)
        for decision in report.security_decisions
        if decision.company_id in set(SELECTED_COMPANY_IDS)
    ]
    excluded_security_decisions = [
        security_payload(decision)
        for decision in report.security_decisions
        if not decision.eligible
    ]

    expected = {
        "cvm:6041": "ELIGIBLE_BRAZILIAN_LISTED_EQUITY_ISSUER",
        "cvm:18759": "EXCLUDED_NO_FCA_SECURITY_ROWS",
        "cvm:27634": "ELIGIBLE_BRAZILIAN_LISTED_EQUITY_ISSUER",
        "cvm:7617": "ELIGIBLE_BRAZILIAN_LISTED_EQUITY_ISSUER",
        "cvm:9512": "ELIGIBLE_BRAZILIAN_LISTED_EQUITY_ISSUER",
        "cvm:80195": "EXCLUDED_ISSUER_NOT_ELIGIBLE",
        "cvm:80152": "EXCLUDED_ISSUER_NOT_ELIGIBLE",
    }
    for company_id, status in expected.items():
        decision = company_by_id.get(company_id)
        if decision is None or decision.status != status:
            actual = decision.status if decision is not None else "MISSING"
            raise RuntimeError(
                f"unexpected current security eligibility for {company_id}: "
                f"expected={status} actual={actual}"
            )

    payload = {
        "generated_at": collected_at.isoformat(),
        "year": year,
        "source_contracts": [
            "B3_INDUSTRY_CLASSIFICATION",
            "CVM_CAD",
            "CVM_FOREIGN_ISSUER_CAD",
            "CVM_FCA",
        ],
        "scope": report.scope,
        "point_in_time_eligible": report.point_in_time_eligible,
        "allowed_security_types": [
            "Ações Ordinárias",
            "Ações Preferenciais",
            "Units",
        ],
        "candidate_company_ids": report.candidate_company_ids,
        "latest_candidate_security_rows": report.latest_security_rows,
        "eligible_company_ids": len(report.eligible_company_ids),
        "eligible_tickers": len(report.eligible_tickers),
        "company_status_counts": report.company_status_counts,
        "security_status_counts": report.security_status_counts,
        "selected_company_decisions": selected_companies,
        "selected_security_decisions": selected_security_decisions,
        "excluded_company_decisions": excluded_companies,
        "excluded_security_decisions": excluded_security_decisions,
        "unmapped_security_tickers_sample": list(
            cvm_service.last_unmapped_security_tickers[:20]
        ),
        "eligible_security_row_count": len(eligible_securities),
        "notes": [
            "Eligibility is current-state only and must not be backfilled into historical tests.",
            "Issuer identity and jurisdiction are resolved before security-level eligibility.",
            "Ticker suffixes and issuer/security names are never used to infer eligibility.",
            "Units are explicitly supported as listed Brazilian equity securities; subscription bonuses are not.",
            "All current company and security exclusions are emitted for audit before merge.",
        ],
    }
    Path("current-brazilian-equity-security-universe.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
