from __future__ import annotations

import argparse
import json
from datetime import UTC, date, datetime
from pathlib import Path
from urllib.parse import urlparse

import httpx

from ultimate_stock_analyzer.backtesting.cvm_enet_public_document_status_audit import (
    ENET_PUBLIC_LIST_URL,
    ENET_PUBLIC_PAGE_URL,
    PILLAR3_IPE_DOCUMENT_ACTION_HISTORY_UNPROVEN,
    ENETPublicQueryProbeInput,
    audit_cvm_enet_public_document_status,
)
from ultimate_stock_analyzer.backtesting.cvm_ipe_pillar3_filing_ledger import (
    BANK_EVIDENCE_NOT_POINT_IN_TIME,
    PILLAR3_IPE_REVISION_HISTORY_COMPLETENESS_UNPROVEN,
)

CVM_CODE = 19348
DELIVERY_DATES = (
    date(2025, 2, 5),
    date(2025, 3, 31),
    date(2026, 2, 4),
    date(2026, 3, 31),
)
_MAX_RESPONSE_BYTES = 2_000_000
_ALLOWED_HOSTS = {"www.rad.cvm.gov.br", "rad.cvm.gov.br"}


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Probe the public CVM ENET document grid for bounded Pillar 3 status "
            "evidence without claiming historical action-timeline completeness."
        )
    )
    parser.add_argument(
        "--output",
        default="cvm-enet-public-document-status-audit.json",
    )
    return parser


def _modern_query_payload(delivery_date: date) -> dict[str, str]:
    day = delivery_date.strftime("%d/%m/%Y")
    return {
        "dataDe": day,
        "dataAte": day,
        "empresa": "",
        "setorAtividade": "-1",
        "categoriaEmissor": "-1",
        "situacaoEmissor": "-1",
        "tipoParticipante": "-1",
        "dataReferencia": "",
        "categoria": "-1",
        "periodo": "0",
        "horaIni": "",
        "horaFim": "",
        "palavraChave": "Pilar 3",
        "ultimaDtRef": "false",
        "tipoEmpresa": "0",
    }


def _bounded_post(
    client: httpx.Client,
    *,
    delivery_date: date,
) -> ENETPublicQueryProbeInput:
    try:
        with client.stream(
            "POST",
            ENET_PUBLIC_LIST_URL,
            json=_modern_query_payload(delivery_date),
            headers={
                "Accept": "application/json, text/javascript, */*; q=0.01",
                "Content-Type": "application/json; charset=utf-8",
                "X-Requested-With": "XMLHttpRequest",
                "Referer": ENET_PUBLIC_PAGE_URL,
            },
        ) as response:
            chunks: list[bytes] = []
            captured = 0
            complete = True
            for chunk in response.iter_bytes():
                remaining = _MAX_RESPONSE_BYTES - captured
                if remaining <= 0:
                    complete = False
                    break
                if len(chunk) > remaining:
                    chunks.append(chunk[:remaining])
                    complete = False
                    break
                chunks.append(chunk)
                captured += len(chunk)
            return ENETPublicQueryProbeInput(
                delivery_date=delivery_date,
                requested_url=ENET_PUBLIC_LIST_URL,
                final_url=str(response.url),
                status_code=response.status_code,
                content_type=response.headers.get("content-type"),
                content=b"".join(chunks),
                body_complete=complete,
            )
    except httpx.HTTPError as error:
        return ENETPublicQueryProbeInput(
            delivery_date=delivery_date,
            requested_url=ENET_PUBLIC_LIST_URL,
            final_url=None,
            status_code=None,
            content_type=None,
            content=None,
            transport_error=f"{type(error).__name__}: {error}",
        )


def _bootstrap_public_session(client: httpx.Client) -> dict[str, object]:
    response = client.get(
        ENET_PUBLIC_PAGE_URL,
        params={"codigoCVM": str(CVM_CODE), "tipoconsulta": "CVM"},
    )
    parsed = urlparse(str(response.url))
    trusted = bool(
        200 <= response.status_code < 300
        and parsed.scheme == "https"
        and parsed.hostname in _ALLOWED_HOSTS
        and parsed.path.casefold() == urlparse(ENET_PUBLIC_PAGE_URL).path.casefold()
    )
    return {
        "requested_url": str(response.request.url),
        "final_url": str(response.url),
        "status_code": response.status_code,
        "content_type": response.headers.get("content-type"),
        "trusted": trusted,
    }


def main() -> None:
    args = _parser().parse_args()
    generated_at = datetime.now(UTC)
    probes: list[ENETPublicQueryProbeInput] = []
    with httpx.Client(
        timeout=120.0,
        follow_redirects=False,
        headers={"User-Agent": "ultimate-stock-analyzer/1.0"},
    ) as client:
        bootstrap = _bootstrap_public_session(client)
        if bootstrap["trusted"]:
            probes.extend(
                _bounded_post(client, delivery_date=item) for item in DELIVERY_DATES
            )
        else:
            probes.extend(
                ENETPublicQueryProbeInput(
                    delivery_date=item,
                    requested_url=ENET_PUBLIC_LIST_URL,
                    final_url=None,
                    status_code=None,
                    content_type=None,
                    content=None,
                    transport_error="public ENET session bootstrap was not trusted",
                )
                for item in DELIVERY_DATES
            )

    audit = audit_cvm_enet_public_document_status(
        cvm_code=CVM_CODE,
        probes=probes,
        generated_at=generated_at,
    )
    report = audit.to_dict()
    report["session_bootstrap"] = bootstrap
    report["request_contract"] = {
        "name": "enetweb-public-grid-observed-modern-v1",
        "method": "POST",
        "endpoint": ENET_PUBLIC_LIST_URL,
        "date_windows": [item.isoformat() for item in DELIVERY_DATES],
        "date_window_days": 1,
        "keyword": "Pilar 3",
        "server_side_company_filter_used": False,
        "local_target_cvm_code": CVM_CODE,
        "max_response_bytes_per_query": _MAX_RESPONSE_BYTES,
        "redirects_followed": False,
    }
    report["warnings"] = [
        "ENET_WEBMETHOD_PATH_IS_EMPIRICALLY_PROBED_NOT_TREATED_AS_STABLE_API",
        "CURRENT_PUBLIC_STATUS_IS_NOT_HISTORICAL_ACTION_TIMELINE",
        "IPE_VERSION_SEQUENCE_AND_ENET_STATUS_ARE_SEPARATE EVIDENCE CONTRACTS",
        "NO_BANK_EVIDENCE_OR_READINESS_PROMOTION_IN_THIS BLOCK",
    ]

    required = {
        BANK_EVIDENCE_NOT_POINT_IN_TIME,
        PILLAR3_IPE_REVISION_HISTORY_COMPLETENESS_UNPROVEN,
        PILLAR3_IPE_DOCUMENT_ACTION_HISTORY_UNPROVEN,
    }
    if not required.issubset(audit.blockers):
        raise RuntimeError("fail-closed IPE/ENET PIT blockers must remain")
    if audit.historical_action_timeline_proven:
        raise RuntimeError("public current-status probe cannot prove action history")
    if audit.revision_history_completeness_proven:
        raise RuntimeError("public current-status probe cannot prove revision completeness")
    if audit.bank_evidence_point_in_time_ready or audit.readiness_promotion_allowed:
        raise RuntimeError("diagnostic ENET probe cannot promote bank readiness")

    Path(args.output).write_text(
        json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True),
        encoding="utf-8",
    )
    print(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
