from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from ultimate_stock_analyzer.collectors.bcb_ifdata import BCBIFDataCollector
from ultimate_stock_analyzer.orchestration.cvm_ingestion import CVMIngestionService
from ultimate_stock_analyzer.scoring.ifdata_applicability_audit import (
    audit_ifdata_issuer_applicability,
)

FIGE_COMPANY_ID = "cvm:6041"


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Audit whether FIGE's canonical CVM issuer identity resolves exactly "
            "to a BCB IFData prudential conglomerate."
        )
    )
    parser.add_argument("--year", type=int, default=2025)
    parser.add_argument(
        "--output",
        default="fige-ifdata-applicability-audit.json",
    )
    args = parser.parse_args()

    collected_at = datetime.now(UTC)
    issuers = CVMIngestionService().load_issuer_master(
        collected_at=collected_at,
        active_only=False,
    )
    matches = [issuer for issuer in issuers if issuer.company_id == FIGE_COMPANY_ID]
    if len(matches) != 1:
        raise RuntimeError(
            "Expected exactly one canonical CVM issuer for FIGE: "
            f"company_id={FIGE_COMPANY_ID} count={len(matches)}"
        )
    issuer = matches[0]
    if not issuer.cnpj:
        raise RuntimeError(
            f"Canonical CVM issuer has no CNPJ: company_id={FIGE_COMPANY_ID}"
        )

    collector = BCBIFDataCollector()
    ano_mes = args.year * 100 + 12
    cadastro = collector.download_cadastro(ano_mes)
    identity_audit = audit_ifdata_issuer_applicability(
        issuer=issuer,
        cadastro_content=cadastro,
        ano_mes=ano_mes,
    )

    final_audit = identity_audit
    collection_warnings: tuple[str, ...] = ()
    if identity_audit.prudential_identity is not None:
        collection = collector.collect_annual_bank_profiles(
            (issuer,),
            fiscal_year=args.year,
            collected_at=collected_at,
        )
        collection_warnings = collection.warnings
        profiles = [
            profile
            for profile in collection.profiles
            if profile.company_id == FIGE_COMPANY_ID
        ]
        if len(profiles) != 1:
            raise RuntimeError(
                "Exact IFData identity was found but annual bank profile count is "
                f"unexpected: company_id={FIGE_COMPANY_ID} count={len(profiles)}"
            )
        final_audit = audit_ifdata_issuer_applicability(
            issuer=issuer,
            cadastro_content=cadastro,
            ano_mes=ano_mes,
            profile=profiles[0],
        )

    payload = {
        "generated_at": collected_at.isoformat(),
        "fiscal_year": args.year,
        "source_contracts": ["CVM_CAD", "BCB_IFDATA"],
        "audit": final_audit.to_dict(),
        "collection_warnings": list(collection_warnings),
        "notes": [
            "Issuer identity is established only by canonical CVM company_id and official CNPJ.",
            "BCB IFData applicability uses the existing exact leader-CNPJ-root prudential-conglomerate join; issuer name, ticker and fuzzy matching are not used.",
            "NO_PRUDENTIAL_IDENTITY is a valid diagnostic outcome and is not converted into an inferred bank match.",
            "A bank profile is collected only after an exact prudential identity is found.",
            "The latest-state IFData source is not revision-aware point-in-time evidence for strict historical backtests.",
        ],
    }
    Path(args.output).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, default=str)
        + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
