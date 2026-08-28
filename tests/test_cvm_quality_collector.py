import io
import zipfile

import pytest

from ultimate_stock_analyzer.collectors.cvm_quality import (
    CVMStructuredZipCollector,
    parse_cvm_structured_zip,
    select_dataset,
)


def _fixture_zip() -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("fre_cia_auditor_2026.csv", "CD_CVM;AUDITOR\n123;Auditoria Exemplo\n")
        archive.writestr("ignore.txt", "not a csv")
    return buffer.getvalue()


def test_structured_zip_preserves_raw_columns() -> None:
    datasets = parse_cvm_structured_zip(_fixture_zip())
    rows = select_dataset(datasets, "auditor")
    assert rows == [{"CD_CVM": "123", "AUDITOR": "Auditoria Exemplo"}]


def test_collector_rejects_non_official_host() -> None:
    collector = CVMStructuredZipCollector()
    with pytest.raises(ValueError, match="official"):
        collector.fetch("https://example.com/file.zip")
