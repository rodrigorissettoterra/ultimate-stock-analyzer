from __future__ import annotations

import json
from datetime import UTC, datetime
from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile

import pytest
from openpyxl import Workbook

from ultimate_stock_analyzer.collectors.b3_classification import (
    B3IndustryClassificationCollector,
)


def _workbook_bytes() -> bytes:
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "Planilha"
    worksheet["B2"] = "SETOR"
    worksheet["C2"] = "SUBSETOR"
    worksheet["D2"] = "SEGMENTO"
    worksheet["E2"] = "EMISSOR"
    worksheet["E3"] = "NOME DE PREGÃO"
    worksheet["F3"] = "CÓDIGO"
    worksheet["G3"] = "SEGMENTO DE NEGOCIAÇÃO"
    worksheet.append([None, "Petróleo, Gás e Biocombustíveis", "Petróleo, Gás e Biocombustíveis", "Exploração, Refino e Distribuição", "PETROBRAS", "PETR", "Nível 2"])
    worksheet.append([None, "Financeiro", "Intermediários Financeiros", "Bancos", "ITAUUNIBANCO", "ITUB", "Nível 1"])
    output = BytesIO()
    workbook.save(output)
    workbook.close()
    return output.getvalue()


def _catalog_archive(*, conflicting: bool = False) -> bytes:
    results = [
        {
            "status": "A",
            "issuingCompany": "PETR",
            "codeCVM": "9512",
            "cnpj": "33.000.167/0001-01",
        },
        {
            "status": "A",
            "issuingCompany": "ITUB",
            "codeCVM": "19348",
            "cnpj": "60.872.504/0001-23",
        },
    ]
    if conflicting:
        results.append(
            {
                "status": "A",
                "issuingCompany": "ITUB",
                "codeCVM": "99999",
                "cnpj": "60.872.504/0001-23",
            }
        )
    payload = {
        "page": {
            "pageNumber": 1,
            "pageSize": 100,
            "totalPages": 1,
            "totalRecords": len(results),
        },
        "results": results,
    }
    output = BytesIO()
    with ZipFile(output, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr("page_0001.json", json.dumps(payload))
    return output.getvalue()


def test_b3_classification_normalizes_official_identity_chain() -> None:
    collector = B3IndustryClassificationCollector()
    rows = collector.normalize(
        _workbook_bytes(),
        _catalog_archive(),
        collected_at=datetime(2026, 8, 29, 22, tzinfo=UTC),
    )

    by_company = {row.company_id: row for row in rows}
    petrobras = by_company["cvm:9512"]
    assert petrobras.issuer_code == "PETR"
    assert petrobras.sector == "Petróleo, Gás e Biocombustíveis"
    assert petrobras.segment == "Exploração, Refino e Distribuição"
    assert petrobras.listing_segment == "Nível 2"
    assert petrobras.cnpj == "33000167000101"
    assert petrobras.point_in_time_eligible is False

    itau = by_company["cvm:19348"]
    assert itau.subsector == "Intermediários Financeiros"
    assert itau.segment == "Bancos"
    assert collector.last_unmapped_issuer_codes == ()


def test_b3_classification_fails_closed_on_conflicting_active_cvm_identity() -> None:
    collector = B3IndustryClassificationCollector()
    with pytest.raises(ValueError, match="multiple active CVM identities"):
        collector.normalize(
            _workbook_bytes(),
            _catalog_archive(conflicting=True),
            collected_at=datetime(2026, 8, 29, 22, tzinfo=UTC),
        )
