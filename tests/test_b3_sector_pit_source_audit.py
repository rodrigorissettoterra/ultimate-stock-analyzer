import io
import zipfile
from datetime import UTC, datetime

import pytest

from ultimate_stock_analyzer.backtesting.b3_sector_pit_source_audit import (
    B3_CLASSIFICATION_AS_OF_CONTRACT_UNAVAILABLE,
    B3_CLASSIFICATION_CURRENT_SNAPSHOT_ONLY,
    B3_CLASSIFICATION_REVISION_HISTORY_UNAVAILABLE,
    HISTORICAL_SECTOR_ROUTING_SOURCE_UNPROVEN,
    audit_b3_sector_pit_source,
)


def _workbook(*, shared_text: str = "SETOR") -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr(
            "xl/workbook.xml",
            '<?xml version="1.0"?><workbook><sheets><sheet name="Planilha"/></sheets></workbook>',
        )
        archive.writestr(
            "xl/worksheets/sheet1.xml",
            '<?xml version="1.0"?><worksheet><sheetData/></worksheet>',
        )
        archive.writestr(
            "xl/sharedStrings.xml",
            f'<?xml version="1.0"?><sst><si><t>{shared_text}</t></si></sst>',
        )
    return output.getvalue()


def _audit(content: bytes | None = None):
    return audit_b3_sector_pit_source(
        workbook_content=content or _workbook(),
        classification_record_count=371,
        collected_at=datetime(2026, 9, 2, tzinfo=UTC),
        source_page_url=(
            "https://www.b3.com.br/pt_br/produtos-e-servicos/negociacao/"
            "renda-variavel/acoes/consultas/classificacao-setorial/"
        ),
        requested_start_year=2024,
        requested_end_year=2025,
    )


def test_current_workbook_can_start_forward_lineage_but_cannot_backfill_history() -> None:
    audit = _audit()

    assert audit.classification_record_count == 371
    assert audit.current_snapshot_point_in_time_from_collection
    assert audit.historical_snapshot_count == 0
    assert audit.requested_years_covered == 0
    assert not audit.historical_backfill_ready
    assert not audit.sector_routing_point_in_time_ready
    assert not audit.readiness_promotion_allowed
    assert B3_CLASSIFICATION_CURRENT_SNAPSHOT_ONLY in audit.blockers
    assert B3_CLASSIFICATION_AS_OF_CONTRACT_UNAVAILABLE in audit.blockers
    assert B3_CLASSIFICATION_REVISION_HISTORY_UNAVAILABLE in audit.blockers
    assert HISTORICAL_SECTOR_ROUTING_SOURCE_UNPROVEN in audit.blockers


def test_unlabelled_workbook_date_literal_is_not_promoted_to_contractual_as_of_date() -> None:
    audit = _audit(_workbook(shared_text="arquivo 31/08/2026"))

    assert audit.embedded_date_literals == ("2026-08-31",)
    assert audit.contractual_as_of_date is None
    assert not audit.sector_routing_point_in_time_ready


def test_audit_records_hash_and_archive_shape() -> None:
    content = _workbook()
    audit = _audit(content)

    assert len(audit.workbook_sha256) == 64
    assert audit.workbook_size_bytes == len(content)
    assert audit.workbook_member_count == 3
    assert not audit.core_properties_present
    assert audit.embedded_date_literals == ()


def test_audit_rejects_non_official_source_and_non_xlsx_content() -> None:
    with pytest.raises(ValueError, match="official B3 HTTPS host"):
        audit_b3_sector_pit_source(
            workbook_content=_workbook(),
            classification_record_count=1,
            collected_at=datetime(2026, 9, 2, tzinfo=UTC),
            source_page_url="https://example.com/classification",
            requested_start_year=2024,
            requested_end_year=2025,
        )
    with pytest.raises(ValueError, match="XLSX archive"):
        _audit(b"not-a-workbook")


def test_report_serialization_preserves_fail_closed_dates() -> None:
    payload = _audit().to_dict()

    assert payload["collected_at"] == "2026-09-02T00:00:00+00:00"
    assert payload["contractual_as_of_date"] is None
    assert payload["embedded_date_literals"] == []
    assert payload["requested_start_year"] == 2024
