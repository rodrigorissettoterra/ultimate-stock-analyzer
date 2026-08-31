from __future__ import annotations

import json
from collections import Counter
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from ultimate_stock_analyzer.collectors.b3_classification import (
    B3IndustryClassificationCollector,
)
from ultimate_stock_analyzer.market.prices import B3CotahistCollector
from ultimate_stock_analyzer.orchestration.cvm_ingestion import CVMIngestionService
from ultimate_stock_analyzer.universe.multiyear_security_audit import (
    audit_multiyear_fca_against_cotahist,
)

REVIEW_COMPANY_IDS = (
    "cvm:15091",  # LTEL
    "cvm:16608",  # EQMA
    "cvm:17949",  # MRSA
    "cvm:18414",  # PDTC
    "cvm:18759",  # BSCS
    "cvm:18775",  # IVPR
    "cvm:19232",  # PRMN
    "cvm:21008",  # GSHP
    "cvm:21180",  # NEXP
    "cvm:23515",  # AGRU
    "cvm:23523",  # PSVM
    "cvm:24236",  # PRNR
    "cvm:24759",  # LTLA
    "cvm:24848",  # CEAB
    "cvm:25542",  # LLBI
    "cvm:25895",  # WDCN
    "cvm:25917",  # RAIZ
    "cvm:26034",  # MLAS
    "cvm:26280",  # COMR
    "cvm:27219",  # EGGY
    "cvm:27693",  # BRST
    "cvm:3395",   # CATA
    "cvm:4081",   # CTSA
    "cvm:8036",   # LIGH
)
POSITIVE_CONTROL_COMPANY_ID = "cvm:9512"  # Petrobras


def main() -> None:
    collected_at = datetime.now(UTC)
    cotahist_year = collected_at.year
    fca_years = tuple(range(cotahist_year - 4, cotahist_year + 1))

    b3_collector = B3IndustryClassificationCollector()
    classifications = b3_collector.normalize(
        b3_collector.download_workbook(),
        b3_collector.download_company_catalog_archive(),
        collected_at=collected_at,
    )
    classification_by_company = {
        record.company_id: record
        for record in classifications
    }
    candidate_company_ids = tuple(classification_by_company)

    cvm_service = CVMIngestionService()
    cvm_service.load_issuer_master(
        collected_at=collected_at,
        active_only=False,
    )

    securities_by_year = {}
    unmapped_by_year: dict[int, tuple[str, ...]] = {}
    all_fca_tickers: set[str] = set()
    for year in fca_years:
        securities = cvm_service.load_security_master(
            year=year,
            collected_at=collected_at,
        )
        securities_by_year[year] = securities
        unmapped_by_year[year] = cvm_service.last_unmapped_security_tickers
        all_fca_tickers.update(
            security.ticker.strip().upper()
            for security in securities
            if security.ticker.strip()
        )

    cotahist_bars = B3CotahistCollector(timeout_seconds=120.0).fetch_year(
        cotahist_year,
        tickers=all_fca_tickers,
    )
    report = audit_multiyear_fca_against_cotahist(
        candidate_company_ids,
        securities_by_year,
        cotahist_bars,
        cotahist_year=cotahist_year,
    )

    company_by_id = {
        evidence.company_id: evidence
        for evidence in report.company_evidence
    }
    ticker_evidence_by_company: dict[str, list[object]] = {}
    for evidence in report.ticker_evidence:
        ticker_evidence_by_company.setdefault(evidence.company_id, []).append(evidence)

    current_year_company_ids = {
        security.company_id
        for security in securities_by_year[cotahist_year]
    }

    def company_payload(company_id: str) -> dict[str, object]:
        evidence = company_by_id[company_id]
        classification = classification_by_company.get(company_id)
        payload: dict[str, object] = asdict(evidence)
        payload["current_year_fca_presence"] = company_id in current_year_company_ids
        if classification is not None:
            payload.update(
                {
                    "issuer_code": classification.issuer_code,
                    "trading_name": classification.trading_name,
                    "sector": classification.sector,
                    "subsector": classification.subsector,
                    "segment": classification.segment,
                }
            )
        return payload

    review_company_evidence = [
        company_payload(company_id)
        for company_id in REVIEW_COMPANY_IDS
        if company_id in company_by_id
    ]
    review_ticker_evidence = [
        asdict(evidence)
        for company_id in REVIEW_COMPANY_IDS
        for evidence in ticker_evidence_by_company.get(company_id, ())
    ]
    candidate_review_required = [
        company_payload(evidence.company_id)
        for evidence in report.company_evidence
        if evidence.status != "TRADED_EXACT_FCA_TICKER"
    ]

    specification_counts = Counter()
    security_type_counts = Counter()
    for evidence in report.ticker_evidence:
        if evidence.cotahist_trade_days <= 0:
            continue
        for specification in evidence.b3_specifications:
            specification_counts[specification] += 1
        security_type_counts[evidence.latest_fca_security_type or "<MISSING>"] += 1

    recovered_from_current_year_gap = sorted(
        evidence.company_id
        for evidence in report.company_evidence
        if evidence.company_id in REVIEW_COMPANY_IDS
        and evidence.status == "TRADED_EXACT_FCA_TICKER"
        and evidence.company_id not in current_year_company_ids
    )

    payload = {
        "generated_at": collected_at.isoformat(),
        "scope": report.scope,
        "point_in_time_eligible": report.point_in_time_eligible,
        "sources": {
            "fca": "CVM FCA structured open data, rolling five-year filing window",
            "cotahist": "B3 COTAHIST annual historical quotations",
            "b3_classification": "B3 current industry-classification snapshot",
        },
        "fca_years": list(report.fca_years),
        "cotahist_year": report.cotahist_year,
        "candidate_company_ids": report.candidate_company_ids,
        "fca_security_rows": report.fca_security_rows,
        "unique_fca_tickers": report.unique_fca_tickers,
        "ticker_identity_conflicts": report.ticker_identity_conflicts,
        "cotahist_matching_rows": report.cotahist_matching_rows,
        "cotahist_latest_trade_date": (
            report.cotahist_latest_trade_date.isoformat()
            if report.cotahist_latest_trade_date is not None
            else None
        ),
        "company_status_counts": report.company_status_counts,
        "companies_with_exact_trading_evidence": len(
            report.companies_with_exact_trading_evidence
        ),
        "companies_without_fca_ticker_history": list(
            report.companies_without_fca_ticker_history
        ),
        "companies_without_2026_spot_trade": list(
            report.companies_without_2026_spot_trade
        ),
        "review_company_evidence": review_company_evidence,
        "review_ticker_evidence": review_ticker_evidence,
        "candidate_company_evidence_requiring_review": candidate_review_required,
        "recovered_review_companies_missing_from_current_year_fca": (
            recovered_from_current_year_gap
        ),
        "b3_specification_counts_for_traded_exact_fca_tickers": dict(
            sorted(specification_counts.items())
        ),
        "latest_fca_security_type_counts_for_traded_exact_fca_tickers": dict(
            sorted(security_type_counts.items())
        ),
        "unmapped_fca_tickers_by_year": {
            str(year): list(tickers)
            for year, tickers in sorted(unmapped_by_year.items())
            if tickers
        },
        "notes": [
            "This is a diagnostic cross-source audit, not a security eligibility rule.",
            "FCA is used only for exact ticker-to-company identity and metadata history.",
            "B3 COTAHIST is used as direct evidence that an exact FCA ticker traded "
            "in the spot market during the current year.",
            "No ticker-prefix, issuer-name, suffix, fuzzy or heuristic identity inference is used.",
            "Current FCA market/administrator/activity fields are intentionally not "
            "treated as decisive when direct B3 trading evidence exists.",
            "The artifact is current-state evidence and is not point-in-time eligible "
            "for historical backtests.",
        ],
    }

    output = Path("fca-cotahist-multiyear-security-audit.json")
    output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, default=str)
        + "\n",
        encoding="utf-8",
    )

    control = company_by_id.get(POSITIVE_CONTROL_COMPANY_ID)
    if control is None or control.status != "TRADED_EXACT_FCA_TICKER":
        actual = control.status if control is not None else "MISSING"
        raise RuntimeError(
            "Petrobras positive control did not resolve to direct B3 trading evidence: "
            f"{actual}"
        )
    if report.cotahist_latest_trade_date is None:
        raise RuntimeError("B3 COTAHIST produced no matching current-year trade evidence")


if __name__ == "__main__":
    main()
