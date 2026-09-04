from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest

from ultimate_stock_analyzer.backtesting.bcb_pillar3_dasfn_catalog_snapshot_audit import (
    PILLAR3_DASFN_CATALOG_PAGE_UNAVAILABLE,
    PILLAR3_DASFN_CATALOG_SNAPSHOT_CONTRACT_UNUSABLE,
    PILLAR3_DASFN_CATALOG_SNAPSHOT_INCOMPLETE,
    PILLAR3_DASFN_LOCAL_FILTER_NO_ROWS,
    PILLAR3_DASFN_LOCAL_FILTER_ROW_UNUSABLE,
    PILLAR3_DASFN_SNAPSHOT_FINAL_URL_UNTRUSTED,
    Pillar3DASFNCatalogPageInput,
    audit_bcb_pillar3_dasfn_catalog_snapshot,
)

CATALOG_URL = (
    "https://olinda.bcb.gov.br/olinda/servico/"
    "DASFN/versao/v1/odata/Recursos"
)
CENTRAL_SELECT = "Api,Versao,CnpjInstituicao,Recurso,URLDados"
COLLECTED_AT = datetime(2026, 9, 4, tzinfo=UTC)


def _row(
    *,
    api: str = "pilar3",
    version: str = "2.0.1",
    cnpj: str = "60701190000104",
    resource: str = "/km1/v2/{trimestre}",
    data_url: str = "https://example.invalid/pillar3/km1",
) -> dict[str, str]:
    return {
        "Api": api,
        "Versao": version,
        "CnpjInstituicao": cnpj,
        "Recurso": resource,
        "URLDados": data_url,
    }


def _page(
    skip: int,
    top: int,
    rows: list[dict[str, object]] | None = None,
    *,
    status: int = 200,
    final_url: str | None = None,
    raw_content: bytes | None = None,
    transport_error: str | None = None,
    extra_query: str = "",
) -> Pillar3DASFNCatalogPageInput:
    requested_url = (
        f"{CATALOG_URL}?%24format=json&%24select={CENTRAL_SELECT}"
        f"&%24top={top}&%24skip={skip}{extra_query}"
    )
    if transport_error is not None:
        return Pillar3DASFNCatalogPageInput(
            skip=skip,
            top=top,
            requested_url=requested_url,
            final_url=None,
            status_code=None,
            content_type=None,
            content=None,
            transport_error=transport_error,
        )
    content = (
        raw_content
        if raw_content is not None
        else json.dumps({"value": rows or []}).encode()
    )
    return Pillar3DASFNCatalogPageInput(
        skip=skip,
        top=top,
        requested_url=requested_url,
        final_url=final_url if final_url is not None else requested_url,
        status_code=status,
        content_type="application/json",
        content=content,
    )


def _audit(pages: list[Pillar3DASFNCatalogPageInput]):
    return audit_bcb_pillar3_dasfn_catalog_snapshot(
        pages=pages,
        collected_at=COLLECTED_AT,
        catalog_source_url=CATALOG_URL,
    )


def test_complete_unfiltered_page_discovers_pillar3_without_pit_promotion() -> None:
    audit = _audit(
        [
            _page(
                0,
                5,
                [
                    _row(version="1.2.0", resource="/km1/{semestre}"),
                    _row(),
                    _row(
                        api="canais_atendimento",
                        version="2.0.1",
                        resource="/branches",
                    ),
                ],
            )
        ]
    )

    assert audit.snapshot_complete
    assert audit.central_contract_usable
    assert audit.local_filter_usable
    assert audit.current_catalog_discovery_ready
    assert len(audit.pillar3_rows) == 2
    assert audit.observed_version_families == ("v1", "v2")
    assert audit.pillar3_rows[0].url_dados
    assert not audit.historical_vintage_query_proven
    assert not audit.historical_replay_ready
    assert not audit.bank_evidence_point_in_time_ready
    assert not audit.readiness_promotion_allowed


def test_two_page_traversal_is_complete_only_after_short_final_page() -> None:
    audit = _audit(
        [
            _page(
                0,
                2,
                [
                    _row(version="1.2.0"),
                    _row(api="pix_saque", version="1.1.1", resource="/"),
                ],
            ),
            _page(2, 2, [_row()]),
        ]
    )

    assert audit.snapshot_complete
    assert audit.total_catalog_rows == 3
    assert audit.current_catalog_discovery_ready


def test_full_last_page_does_not_claim_snapshot_completion() -> None:
    audit = _audit([_page(0, 2, [_row(), _row(version="1.2.0")])])

    assert not audit.snapshot_complete
    assert not audit.current_catalog_discovery_ready
    assert PILLAR3_DASFN_CATALOG_SNAPSHOT_INCOMPLETE in audit.blockers


def test_http_error_preserves_body_provenance_and_fails_closed() -> None:
    audit = _audit([_page(0, 2, status=400, raw_content=b"bad request")])

    evidence = audit.pages[0]
    assert evidence.status_code == 400
    assert evidence.size_bytes == len(b"bad request")
    assert len(evidence.sha256 or "") == 64
    assert not evidence.trusted_http_success
    assert not audit.current_catalog_discovery_ready
    assert PILLAR3_DASFN_CATALOG_PAGE_UNAVAILABLE in audit.blockers


def test_external_redirect_is_preserved_but_not_trusted() -> None:
    audit = _audit(
        [_page(0, 2, [_row()], final_url="https://example.invalid/redirect")]
    )

    assert audit.pages[0].status_code == 200
    assert not audit.pages[0].trusted_http_success
    assert PILLAR3_DASFN_SNAPSHOT_FINAL_URL_UNTRUSTED in audit.blockers
    assert PILLAR3_DASFN_CATALOG_PAGE_UNAVAILABLE in audit.blockers


def test_same_endpoint_redirect_with_changed_query_is_not_trusted() -> None:
    final_url = (
        f"{CATALOG_URL}?%24format=json&%24select={CENTRAL_SELECT}"
        "&%24top=2&%24skip=0&%24filter=Api%20eq%20%27pilar3%27"
    )
    audit = _audit([_page(0, 2, [_row()], final_url=final_url)])

    assert audit.pages[0].status_code == 200
    assert not audit.pages[0].trusted_http_success
    assert PILLAR3_DASFN_SNAPSHOT_FINAL_URL_UNTRUSTED in audit.blockers
    assert PILLAR3_DASFN_CATALOG_PAGE_UNAVAILABLE in audit.blockers
    assert not audit.current_catalog_discovery_ready


def test_transport_error_does_not_fabricate_http_body_provenance() -> None:
    audit = _audit([_page(0, 2, transport_error="ReadTimeout: timed out")])

    evidence = audit.pages[0]
    assert evidence.status_code is None
    assert evidence.sha256 is None
    assert evidence.size_bytes == 0
    assert evidence.transport_error == "ReadTimeout: timed out"


def test_malformed_json_blocks_central_snapshot_contract() -> None:
    audit = _audit([_page(0, 2, raw_content=b"{broken")])

    assert not audit.central_contract_usable
    assert not audit.current_catalog_discovery_ready
    assert PILLAR3_DASFN_CATALOG_SNAPSHOT_CONTRACT_UNUSABLE in audit.blockers


def test_malformed_non_pillar_row_blocks_whole_snapshot_contract() -> None:
    malformed = _row(api="canais_atendimento", version="2.0.1")
    malformed.pop("Api")
    audit = _audit([_page(0, 3, [_row(), malformed])])

    assert not audit.central_contract_usable
    assert not audit.current_catalog_discovery_ready
    assert PILLAR3_DASFN_CATALOG_SNAPSHOT_CONTRACT_UNUSABLE in audit.blockers


def test_generic_url_cannot_replace_central_urldados() -> None:
    malformed = _row()
    malformed["Url"] = malformed.pop("URLDados")
    audit = _audit([_page(0, 3, [malformed])])

    assert not audit.central_contract_usable
    assert not audit.current_catalog_discovery_ready


def test_unknown_pillar3_version_blocks_local_filter_without_hiding_structure() -> None:
    audit = _audit([_page(0, 3, [_row(version="10.0.0")])])

    assert audit.central_contract_usable
    assert not audit.local_filter_usable
    assert not audit.current_catalog_discovery_ready
    assert PILLAR3_DASFN_LOCAL_FILTER_ROW_UNUSABLE in audit.blockers


def test_snapshot_with_no_pillar3_rows_is_not_discovery_ready() -> None:
    audit = _audit(
        [
            _page(
                0,
                3,
                [_row(api="canais_atendimento", version="2.0.1", resource="/branches")],
            )
        ]
    )

    assert audit.central_contract_usable
    assert audit.local_filter_usable
    assert not audit.current_catalog_discovery_ready
    assert PILLAR3_DASFN_LOCAL_FILTER_NO_ROWS in audit.blockers


def test_page_contract_rejects_filter_missing_select_and_metadata_mismatch() -> None:
    with pytest.raises(ValueError, match=r"\$filter"):
        _audit([_page(0, 2, [], extra_query="&%24filter=Api%20eq%20%27pilar3%27")])

    missing_select = Pillar3DASFNCatalogPageInput(
        skip=0,
        top=2,
        requested_url=f"{CATALOG_URL}?%24format=json&%24top=2&%24skip=0",
        final_url=f"{CATALOG_URL}?%24format=json&%24top=2&%24skip=0",
        status_code=200,
        content_type="application/json",
        content=b'{"value":[]}',
    )
    with pytest.raises(ValueError, match="select"):
        _audit([missing_select])

    mismatched_top = Pillar3DASFNCatalogPageInput(
        skip=0,
        top=2,
        requested_url=(
            f"{CATALOG_URL}?%24format=json&%24select={CENTRAL_SELECT}"
            "&%24top=3&%24skip=0"
        ),
        final_url=CATALOG_URL,
        status_code=200,
        content_type="application/json",
        content=b'{"value":[]}',
    )
    with pytest.raises(ValueError, match=r"\$top"):
        _audit([mismatched_top])


def test_sequence_source_and_time_validation_are_fail_closed() -> None:
    with pytest.raises(ValueError, match="contiguous"):
        _audit([_page(1, 2, [_row()])])

    with pytest.raises(ValueError, match="same top"):
        _audit([_page(0, 2, [_row(), _row()]), _page(2, 3, [_row()])])

    with pytest.raises(ValueError, match="timezone-aware"):
        audit_bcb_pillar3_dasfn_catalog_snapshot(
            pages=[_page(0, 2, [_row()])],
            collected_at=COLLECTED_AT.replace(tzinfo=None),
            catalog_source_url=CATALOG_URL,
        )

    with pytest.raises(ValueError, match="official BCB DASFN Recursos"):
        audit_bcb_pillar3_dasfn_catalog_snapshot(
            pages=[_page(0, 2, [_row()])],
            collected_at=COLLECTED_AT,
            catalog_source_url="https://olinda.bcb.gov.br/other",
        )


def test_serialization_preserves_diagnostic_boundary() -> None:
    payload = _audit([_page(0, 3, [_row()])]).to_dict()

    assert payload["schema_version"] == "0.1"
    assert (
        payload["effect"]
        == "diagnostic_only_dasfn_unfiltered_snapshot_no_readiness_change"
    )
    assert payload["pillar3_rows"][0]["url_dados"].startswith("https://")
    assert payload["historical_replay_ready"] is False
    assert payload["bank_evidence_point_in_time_ready"] is False
    assert payload["readiness_promotion_allowed"] is False
