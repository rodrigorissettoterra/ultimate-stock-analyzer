from datetime import UTC, date, datetime

import pytest

from ultimate_stock_analyzer.collectors.b3_company_detail import (
    B3ListedCompanyDetailCollector,
)


def test_b3_get_detail_parser_preserves_exact_identity_and_security_codes() -> None:
    collector = B3ListedCompanyDetailCollector()
    detail = collector.parse(
        {
            "codeCVM": "9512",
            "cnpj": "33.000.167/0001-01",
            "companyName": "PETROLEO BRASILEIRO S.A.",
            "tradingName": "PETROBRAS",
            "issuingCompany": "PETR",
            "code": "PETR4",
            "dateQuotation": "03/01/2000",
            "hasQuotation": "S",
            "hasBDR": False,
            "otherCodes": [
                {"code": "PETR3", "isin": "BRPETRACNOR9"},
                {"code": "PETR4", "isin": "BRPETRACNPR6"},
                {"code": "PETR-DEB", "isin": "BRPETRDBS000"},
            ],
        },
        expected_cvm_code=9512,
        collected_at=datetime(2026, 8, 31, tzinfo=UTC),
    )

    assert detail.company_id == "cvm:9512"
    assert detail.cnpj == "33000167000101"
    assert detail.share_quotation_start == date(2000, 1, 3)
    assert detail.all_security_codes == ("PETR4", "PETR3", "PETR-DEB")


def test_b3_get_detail_parser_fails_closed_on_unexpected_cvm_identity() -> None:
    with pytest.raises(ValueError, match="unexpected CVM code"):
        B3ListedCompanyDetailCollector().parse(
            {"codeCVM": "2", "otherCodes": []},
            expected_cvm_code=1,
            collected_at=datetime(2026, 8, 31, tzinfo=UTC),
        )
