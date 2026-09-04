from __future__ import annotations

import json
from datetime import UTC, date, datetime

import pytest

from ultimate_stock_analyzer.backtesting.cvm_enet_public_document_status_audit import (
    ENET_PUBLIC_LIST_URL,
    PILLAR3_IPE_DOCUMENT_ACTION_HISTORY_UNPROVEN,
    PILLAR3_IPE_ENET_FINAL_URL_UNTRUSTED,
    PILLAR3_IPE_ENET_PUBLIC_CONTRACT_UNUSABLE,
    PILLAR3_IPE_ENET_PUBLIC_QUERY_UNAVAILABLE,
    PILLAR3_IPE_ENET_RESPONSE_TOO_LARGE,
    PILLAR3_IPE_ENET_TARGET_DOCUMENT_NOT_OBSERVED,
    ENETPublicQueryProbeInput,
    audit_cvm_enet_public_document_status,
)
from ultimate_stock_analyzer.backtesting.cvm_ipe_pillar3_filing_ledger import (
    BANK_EVIDENCE_NOT_POINT_IN_TIME,
    PILLAR3_IPE_REVISION_HISTORY_COMPLETENESS_UNPROVEN,
)

_GENERATED_AT = datetime(2026, 9, 4, 19, 0, tzinfo=UTC)


def _content(
    dados: str,
    *,
    tem_erro: bool = False,
    expirou_sessao: bool = False,
) -> bytes:
    return json.dumps(
        {
            "d": {
                "temErro": tem_erro,
                "expirouSessao": expirou_sessao,
                "msgErro": "erro" if tem_erro else "",
                "dados": dados,
            }
        }
    ).encode()


def _probe(
    *,
    delivery_date: date = date(2025, 3, 31),
    content: bytes | None = None,
    final_url: str | None = ENET_PUBLIC_LIST_URL,
    status_code: int | None = 200,
    body_complete: bool = True,
    transport_error: str | None = None,
) -> ENETPublicQueryProbeInput:
    if content is None and status_code is not None:
        content = _content(
            "19348$&Pilar 3$&Ativo$&V 2$&RE - Reapresentacao Espontanea"
        )
    return ENETPublicQueryProbeInput(
        delivery_date=delivery_date,
        requested_url=ENET_PUBLIC_LIST_URL,
        final_url=final_url,
        status_code=status_code,
        content_type="application/json; charset=utf-8",
        content=content,
        body_complete=body_complete,
        transport_error=transport_error,
    )


def test_observes_public_current_status_without_promoting_pit() -> None:
    audit = audit_cvm_enet_public_document_status(
        cvm_code=19348,
        probes=[_probe()],
        generated_at=_GENERATED_AT,
    )

    assert audit.public_current_status_contract_observed is True
    assert audit.observed_status_tokens == ("ATIVO",)
    assert audit.observed_version_tokens == (2,)
    assert "REAPRESENTACAO ESPONTANEA" in audit.observed_modality_tokens
    assert audit.historical_action_timeline_proven is False
    assert audit.revision_history_completeness_proven is False
    assert audit.bank_evidence_point_in_time_ready is False
    assert audit.readiness_promotion_allowed is False
    assert BANK_EVIDENCE_NOT_POINT_IN_TIME in audit.blockers
    assert PILLAR3_IPE_REVISION_HISTORY_COMPLETENESS_UNPROVEN in audit.blockers
    assert PILLAR3_IPE_DOCUMENT_ACTION_HISTORY_UNPROVEN in audit.blockers


def test_server_error_is_fail_closed_contract_failure() -> None:
    audit = audit_cvm_enet_public_document_status(
        cvm_code=19348,
        probes=[_probe(content=_content("", tem_erro=True))],
        generated_at=_GENERATED_AT,
    )

    assert audit.usable_contract_count == 0
    assert PILLAR3_IPE_ENET_PUBLIC_CONTRACT_UNUSABLE in audit.blockers


def test_missing_target_document_blocks_observation() -> None:
    audit = audit_cvm_enet_public_document_status(
        cvm_code=19348,
        probes=[_probe(content=_content("99999$&Outro documento$&Ativo$&V 1"))],
        generated_at=_GENERATED_AT,
    )

    assert audit.target_document_query_count == 0
    assert PILLAR3_IPE_ENET_TARGET_DOCUMENT_NOT_OBSERVED in audit.blockers


def test_off_host_final_url_is_never_trusted() -> None:
    audit = audit_cvm_enet_public_document_status(
        cvm_code=19348,
        probes=[_probe(final_url="https://example.com/ListarDocumentos")],
        generated_at=_GENERATED_AT,
    )

    assert audit.trusted_query_count == 0
    assert PILLAR3_IPE_ENET_PUBLIC_QUERY_UNAVAILABLE in audit.blockers
    assert PILLAR3_IPE_ENET_FINAL_URL_UNTRUSTED in audit.blockers


def test_truncated_response_is_never_trusted() -> None:
    audit = audit_cvm_enet_public_document_status(
        cvm_code=19348,
        probes=[_probe(body_complete=False)],
        generated_at=_GENERATED_AT,
    )

    assert audit.trusted_query_count == 0
    assert PILLAR3_IPE_ENET_RESPONSE_TOO_LARGE in audit.blockers


def test_transport_error_is_preserved_fail_closed() -> None:
    audit = audit_cvm_enet_public_document_status(
        cvm_code=19348,
        probes=[
            _probe(
                content=None,
                final_url=None,
                status_code=None,
                transport_error="ReadTimeout: bounded probe",
            )
        ],
        generated_at=_GENERATED_AT,
    )

    assert audit.trusted_query_count == 0
    assert PILLAR3_IPE_ENET_PUBLIC_QUERY_UNAVAILABLE in audit.blockers


def test_rejects_wrong_requested_endpoint() -> None:
    probe = ENETPublicQueryProbeInput(
        delivery_date=date(2025, 3, 31),
        requested_url="https://www.rad.cvm.gov.br/other",
        final_url=ENET_PUBLIC_LIST_URL,
        status_code=200,
        content_type="application/json",
        content=_content("19348$&Pilar 3$&Ativo"),
    )

    with pytest.raises(ValueError, match="fixed public ENET"):
        audit_cvm_enet_public_document_status(
            cvm_code=19348,
            probes=[probe],
            generated_at=_GENERATED_AT,
        )
