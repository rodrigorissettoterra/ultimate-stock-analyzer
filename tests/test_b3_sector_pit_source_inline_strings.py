import io
import zipfile
from datetime import UTC, datetime

from ultimate_stock_analyzer.backtesting.b3_sector_pit_source_audit import (
    audit_b3_sector_pit_source,
)


def test_inline_worksheet_date_literal_is_detected_without_becoming_as_of() -> None:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr(
            "xl/workbook.xml",
            '<?xml version="1.0"?><workbook><sheets><sheet name="Planilha"/></sheets></workbook>',
        )
        archive.writestr(
            "xl/worksheets/sheet1.xml",
            (
                '<?xml version="1.0"?><worksheet><sheetData><row r="1">'
                '<c r="A1" t="inlineStr"><is><t>gerado 02/09/2026</t></is></c>'
                "</row></sheetData></worksheet>"
            ),
        )

    audit = audit_b3_sector_pit_source(
        workbook_content=output.getvalue(),
        classification_record_count=1,
        collected_at=datetime(2026, 9, 2, tzinfo=UTC),
        source_page_url="https://www.b3.com.br/classificacao-setorial/",
        requested_start_year=2024,
        requested_end_year=2025,
    )

    assert audit.embedded_date_literals == ("2026-09-02",)
    assert audit.contractual_as_of_date is None
    assert not audit.sector_routing_point_in_time_ready
