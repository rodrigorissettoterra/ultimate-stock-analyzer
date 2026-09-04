from datetime import UTC, date, datetime

from ultimate_stock_analyzer.backtesting.cvm_ipe_pillar3_filing_ledger import (
    BANK_EVIDENCE_NOT_POINT_IN_TIME,
    PILLAR3_IPE_DOWNLOAD_URL_MISSING,
    PILLAR3_IPE_EXACT_DELIVERY_TIMESTAMP_UNAVAILABLE,
    PILLAR3_IPE_HISTORICAL_SNAPSHOT_UNAVAILABLE,
    PILLAR3_IPE_OPEN_DATA_EXPORT_COMPLETENESS_UNPROVEN,
    PILLAR3_IPE_PERIOD_FILING_NOT_FOUND,
    PILLAR3_IPE_PERIOD_TOKEN_AMBIGUOUS,
    PILLAR3_IPE_PERIOD_TOKEN_MISSING,
    PILLAR3_IPE_REVISION_HISTORY_COMPLETENESS_UNPROVEN,
    PILLAR3_PDF_CONTENT_UNVALIDATED,
    PILLAR3_PRUDENTIAL_METRIC_COVERAGE_UNPROVEN,
    CVMIPEArchiveSnapshot,
    audit_cvm_ipe_pillar3_filing_ledger,
)
from ultimate_stock_analyzer.collectors.cvm_ipe import CVMIPEDocument


def _document(
    *,
    company_id: str = "cvm:19348",
    subject: str | None = "Relatório de Pilar 3 - 4T24",
    delivered_on: date = date(2025, 2, 5),
    protocol: str | None = "PROTO-1",
    version: int | None = 1,
    download_url: str | None = "https://www.rad.cvm.gov.br/ENET/doc",
) -> CVMIPEDocument:
    return CVMIPEDocument(
        company_id=company_id,
        cvm_code=int(company_id.split(":")[1]),
        company_name="ITAU UNIBANCO HOLDING S.A.",
        cnpj="60.872.504/0001-23",
        reference_date=delivered_on,
        delivered_on=delivered_on,
        available_from=datetime.combine(
            delivered_on,
            datetime.min.time(),
            tzinfo=UTC,
        ),
        category="Relatório de Pilar 3",
        document_type=None,
        species=None,
        subject=subject,
        presentation_type="AP - Apresentação",
        delivery_protocol=protocol,
        version=version,
        download_url=download_url,
        source_year=delivered_on.year,
    )


def _snapshot(year: int) -> CVMIPEArchiveSnapshot:
    return CVMIPEArchiveSnapshot(
        source_year=year,
        source_url=f"https://dados.cvm.gov.br/ipe_{year}.zip",
        sha256="a" * 64,
        size_bytes=123,
    )


def _audit(documents: list[CVMIPEDocument], dates: list[date]):
    return audit_cvm_ipe_pillar3_filing_ledger(
        cvm_code=19348,
        documents=documents,
        source_archives=[_snapshot(2024), _snapshot(2025), _snapshot(2026)],
        requested_reference_dates=dates,
        generated_at=datetime(2026, 9, 2, tzinfo=UTC),
    )


def test_filters_issuer_and_maps_annual_pillar3_period() -> None:
    audit = _audit(
        [
            _document(company_id="cvm:9999"),
            _document(subject="Documento não relacionado"),
            _document(),
        ],
        [date(2024, 12, 31)],
    )

    assert audit.issuer_document_count == 2
    assert audit.pillar3_candidate_count == 2
    assert audit.mapped_pillar3_candidate_count == 1
    assert audit.covered_reference_period_count == 1
    assert audit.timelines[0].filings[0].period_token == "4T24"
    assert audit.timelines[0].prudential_reference_date == date(2024, 12, 31)


def test_preserves_multiple_filings_in_delivery_order() -> None:
    audit = _audit(
        [
            _document(
                delivered_on=date(2025, 3, 31),
                protocol="PROTO-2",
                version=2,
            ),
            _document(
                delivered_on=date(2025, 2, 5),
                protocol="PROTO-1",
                version=1,
            ),
        ],
        [date(2024, 12, 31)],
    )

    timeline = audit.timelines[0]
    assert [item.document.delivery_protocol for item in timeline.filings] == [
        "PROTO-1",
        "PROTO-2",
    ]
    assert timeline.observed_versions == (1, 2)
    assert audit.periods_with_multiple_observed_filings == 1
    assert audit.multiple_observed_filings_present


def test_missing_period_download_and_period_tokens_fail_closed() -> None:
    audit = _audit(
        [
            _document(subject="Relatório de Pilar 3 sem trimestre"),
            _document(subject="Pilar 3 - 3T24 e 4T24"),
            _document(download_url=None),
        ],
        [date(2024, 12, 31), date(2025, 12, 31)],
    )

    assert PILLAR3_IPE_PERIOD_TOKEN_MISSING in audit.blockers
    assert PILLAR3_IPE_PERIOD_TOKEN_AMBIGUOUS in audit.blockers
    assert PILLAR3_IPE_DOWNLOAD_URL_MISSING in audit.blockers
    assert PILLAR3_IPE_PERIOD_FILING_NOT_FOUND in audit.blockers
    assert not audit.observed_filing_timeline_available


def test_revision_completeness_audit_records_documented_and_missing_contracts() -> None:
    audit = _audit([_document()], [date(2024, 12, 31)])

    proof = audit.revision_completeness_audit
    statuses = {item.finding_code: item.status for item in proof.findings}

    assert proof.state == "UNKNOWN"
    assert statuses["PUBLIC_VERSION_RETENTION_DOCUMENTED"] == "DOCUMENTED"
    assert (
        statuses["REAPRESENTED_AND_CANCELLED_DOCUMENTS_REMAIN_VISIBLE"]
        == "DOCUMENTED"
    )
    assert statuses["OPEN_DATA_ARCHIVE_UPDATE_CONTRACT"] == "DOCUMENTED"
    assert (
        statuses["OPEN_DATA_EXPORT_ALL_VERSION_COMPLETENESS"]
        == "NOT_DOCUMENTED_IN_AUDITED_SOURCE"
    )
    assert (
        statuses["HISTORICAL_AS_OF_SNAPSHOT_CONTRACT"]
        == "NOT_DOCUMENTED_IN_AUDITED_SOURCE"
    )
    assert (
        statuses["EXACT_DELIVERY_TIMESTAMP_IN_PARSED_EXPORT"]
        == "NOT_AVAILABLE_IN_PARSED_CONTRACT"
    )
    assert not audit.revision_history_completeness_proven


def test_diagnostic_never_promotes_bank_readiness() -> None:
    audit = _audit([_document()], [date(2024, 12, 31)])

    required = {
        BANK_EVIDENCE_NOT_POINT_IN_TIME,
        PILLAR3_IPE_EXACT_DELIVERY_TIMESTAMP_UNAVAILABLE,
        PILLAR3_IPE_HISTORICAL_SNAPSHOT_UNAVAILABLE,
        PILLAR3_IPE_OPEN_DATA_EXPORT_COMPLETENESS_UNPROVEN,
        PILLAR3_IPE_REVISION_HISTORY_COMPLETENESS_UNPROVEN,
        PILLAR3_PDF_CONTENT_UNVALIDATED,
        PILLAR3_PRUDENTIAL_METRIC_COVERAGE_UNPROVEN,
    }
    assert required.issubset(audit.blockers)
    assert audit.observed_filing_timeline_available
    assert not audit.revision_history_completeness_proven
    assert not audit.pdf_content_validated
    assert not audit.prudential_metric_coverage_proven
    assert not audit.historical_prudential_source_ready
    assert not audit.bank_evidence_point_in_time_ready
    assert not audit.readiness_promotion_allowed
