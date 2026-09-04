from __future__ import annotations

from datetime import UTC, datetime

import pytest

from ultimate_stock_analyzer.backtesting.bcb_pillar3_dasfn_payload_provenance_audit import (
    BANK_EVIDENCE_NOT_POINT_IN_TIME,
    PILLAR3_DASFN_HISTORICAL_VINTAGE_QUERY_UNPROVEN,
    PILLAR3_DASFN_PAYLOAD_BODY_INCOMPLETE,
    PILLAR3_DASFN_PAYLOAD_FINAL_URL_UNTRUSTED,
    PILLAR3_DASFN_PAYLOAD_JSON_UNUSABLE,
    PILLAR3_DASFN_PAYLOAD_PUBLICATION_TIMESTAMP_UNPROVEN,
    PILLAR3_DASFN_PAYLOAD_SAMPLE_MISSING,
    PILLAR3_DASFN_PAYLOAD_UNAVAILABLE,
    PILLAR3_DASFN_REVISION_HISTORY_UNPROVEN,
    Pillar3InstitutionPayloadProbeInput,
    Pillar3PayloadSampleKey,
    audit_bcb_pillar3_institution_payload_provenance,
)

NOW = datetime(2026, 9, 4, tzinfo=UTC)
CNPJ = "00000000000191"


def _key(year: int) -> Pillar3PayloadSampleKey:
    return Pillar3PayloadSampleKey(CNPJ, year)


def _probe(
    year: int = 2022,
    *,
    status: int | None = 200,
    final_url: str | None = None,
    content: bytes | None = b'{"data":{"version":"1"}}',
    body_complete: bool = True,
    headers: tuple[tuple[str, str], ...] = (),
    transport_error: str | None = None,
) -> Pillar3InstitutionPayloadProbeInput:
    url = f"https://bank.example/pillar3/km1/{year}-4"
    return Pillar3InstitutionPayloadProbeInput(
        cnpj_instituicao=CNPJ,
        reference_year=year,
        version="1.2.0",
        resource="/km1/{trimestre}",
        central_url_dados=url,
        requested_url=url,
        final_url=final_url if final_url is not None else (url if status is not None else None),
        status_code=status,
        content_type="application/json" if status is not None else None,
        response_headers=headers,
        content=content,
        body_complete=body_complete,
        transport_error=transport_error,
    )


def _audit(*probes: Pillar3InstitutionPayloadProbeInput, years: tuple[int, ...] = (2022,)):
    return audit_bcb_pillar3_institution_payload_provenance(
        expected_samples=[_key(year) for year in years],
        probes=list(probes),
        collected_at=NOW,
    )


def test_reachable_historical_json_payload_is_observed_without_pit_promotion() -> None:
    audit = _audit(_probe())

    assert audit.reachable_payload_count == 1
    assert audit.json_usable_payload_count == 1
    assert audit.historical_reference_reachable_count == 1
    assert BANK_EVIDENCE_NOT_POINT_IN_TIME in audit.blockers
    assert PILLAR3_DASFN_PAYLOAD_UNAVAILABLE not in audit.blockers
    assert not audit.payload_publication_timestamp_proven
    assert not audit.revision_history_proven
    assert not audit.historical_vintage_query_proven
    assert not audit.readiness_promotion_allowed


def test_missing_expected_institution_year_is_explicit_blocker() -> None:
    audit = _audit(_probe(), years=(2022, 2025))
    assert PILLAR3_DASFN_PAYLOAD_SAMPLE_MISSING in audit.blockers


def test_successful_off_host_redirect_is_not_trusted() -> None:
    audit = _audit(_probe(final_url="https://cdn.example/payload"))
    assert audit.reachable_payload_count == 0
    assert PILLAR3_DASFN_PAYLOAD_FINAL_URL_UNTRUSTED in audit.blockers
    assert PILLAR3_DASFN_PAYLOAD_UNAVAILABLE in audit.blockers


def test_incomplete_body_is_preserved_and_blocked() -> None:
    audit = _audit(_probe(body_complete=False))
    assert PILLAR3_DASFN_PAYLOAD_BODY_INCOMPLETE in audit.blockers
    assert audit.reachable_payload_count == 0


def test_non_json_success_is_not_usable_payload_evidence() -> None:
    audit = _audit(_probe(content=b"<html>not json</html>"))
    assert PILLAR3_DASFN_PAYLOAD_JSON_UNUSABLE in audit.blockers
    assert audit.json_usable_payload_count == 0


def test_headers_and_revision_like_fields_are_observed_but_never_promoted() -> None:
    audit = _audit(
        _probe(
            headers=(
                ("Last-Modified", "Fri, 01 Aug 2025 10:00:00 GMT"),
                ("ETag", '"abc"'),
                ("Date", "Fri, 04 Sep 2026 10:00:00 GMT"),
            ),
            content=b'{"dataUltimaAtualizacao":"2025-08-01"}',
        )
    )
    payload = audit.payloads[0]
    assert audit.last_modified_observed_count == 1
    assert audit.etag_observed_count == 1
    assert payload.revision_like_json_fields == ("dataUltimaAtualizacao",)
    assert payload.last_modified is not None
    assert payload.etag == '"abc"'
    assert not audit.payload_publication_timestamp_proven
    assert not audit.revision_history_proven


def test_transport_error_preserves_provenance_without_fabricating_http_body() -> None:
    audit = _audit(
        _probe(status=None, content=None, transport_error="ReadTimeout: timed out")
    )
    payload = audit.payloads[0]
    assert payload.status_code is None
    assert payload.sha256 is None
    assert payload.size_bytes == 0
    assert payload.transport_error == "ReadTimeout: timed out"
    assert PILLAR3_DASFN_PAYLOAD_UNAVAILABLE in audit.blockers


def test_current_reference_year_is_not_counted_as_historical_reference() -> None:
    audit = _audit(_probe(year=2026), years=(2026,))
    assert audit.historical_reference_reachable_count == 0


@pytest.mark.parametrize("cnpj", ["", "123", "12.345.678/0001-90", "A" * 14])
def test_invalid_cnpj_is_rejected(cnpj: str) -> None:
    with pytest.raises(ValueError, match="CNPJ"):
        audit_bcb_pillar3_institution_payload_provenance(
            expected_samples=[Pillar3PayloadSampleKey(cnpj, 2022)],
            probes=[],
            collected_at=NOW,
        )


def test_probe_outside_expected_samples_is_rejected() -> None:
    with pytest.raises(ValueError, match="outside expected_samples"):
        audit_bcb_pillar3_institution_payload_provenance(
            expected_samples=[_key(2022)],
            probes=[_probe(2025)],
            collected_at=NOW,
        )


def test_requested_url_must_be_exact_central_urldados() -> None:
    probe = _probe()
    bad = Pillar3InstitutionPayloadProbeInput(
        cnpj_instituicao=probe.cnpj_instituicao,
        reference_year=probe.reference_year,
        version=probe.version,
        resource=probe.resource,
        central_url_dados=probe.central_url_dados,
        requested_url="https://bank.example/other",
        final_url="https://bank.example/other",
        status_code=200,
        content_type="application/json",
        response_headers=(),
        content=b"{}",
        body_complete=True,
    )
    with pytest.raises(ValueError, match="central URLDados"):
        _audit(bad)


def test_serialization_keeps_fail_closed_boundary() -> None:
    report = _audit(_probe()).to_dict()
    assert report["schema_version"] == "0.1"
    assert report["effect"] == "diagnostic_only_pillar3_payload_provenance_no_readiness_change"
    assert report["payload_publication_timestamp_proven"] is False
    assert report["revision_history_proven"] is False
    assert report["readiness_promotion_allowed"] is False
    assert PILLAR3_DASFN_PAYLOAD_PUBLICATION_TIMESTAMP_UNPROVEN in report["blockers"]
    assert PILLAR3_DASFN_REVISION_HISTORY_UNPROVEN in report["blockers"]
    assert PILLAR3_DASFN_HISTORICAL_VINTAGE_QUERY_UNPROVEN in report["blockers"]
