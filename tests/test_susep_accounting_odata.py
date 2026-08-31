from datetime import date
from decimal import Decimal

import pytest

from ultimate_stock_analyzer.collectors.susep_accounting_odata import (
    VERIFIED_ACCOUNTING_RESOURCES,
    SusepAccountingODataService,
)


def test_accounting_row_parses_documented_fields() -> None:
    row = SusepAccountingODataService().parse_accounting_row(
        {
            "entnome": "SEGURADORA TESTE S.A.",
            "cnpj": "12.345.678/0001-90",
            "mesreferencia": "2025-12-01T00:00:00",
            "cmpid": 518,
            "cmptitulo": "(=) LUCRO LÍQUIDO / PREJUÍZO",
            "valor": "1234567.89",
            "cmpnumero": 99,
        }
    )

    assert row.cnpj == "12345678000190"
    assert row.reference_month == date(2025, 12, 1)
    assert row.cmpid == 518
    assert row.value == Decimal("1234567.89")
    assert row.point_in_time_eligible is False


def test_accounting_row_accepts_negative_value() -> None:
    row = SusepAccountingODataService().parse_accounting_row(
        {
            "entnome": "SEGURADORA TESTE S.A.",
            "cnpj": "12345678000190",
            "mesreferencia": "2025-12-01",
            "cmpid": "518",
            "cmptitulo": "LUCRO LÍQUIDO / PREJUÍZO",
            "valor": -50,
        }
    )
    assert row.value == Decimal(-50)


def test_service_document_names_are_exact_and_sorted(monkeypatch) -> None:
    monkeypatch.setattr(
        SusepAccountingODataService,
        "_get_json",
        lambda *_args, **_kwargs: {
            "value": [
                {"name": "DRE", "kind": "EntitySet", "url": "DRE"},
                {"name": "Ativo", "kind": "EntitySet", "url": "Ativo"},
                {"name": "DRE", "kind": "EntitySet", "url": "DRE"},
            ]
        },
    )
    assert SusepAccountingODataService().fetch_resource_names() == ("Ativo", "DRE")


def test_verified_accounting_resources_are_exact() -> None:
    assert VERIFIED_ACCOUNTING_RESOURCES == (
        "ContabeisAtivo",
        "ContabeisPassivo",
        "ContabeisDRE",
        "ContabeisDRER",
        "ContabeisDMPL",
        "ContabeisDMPS",
        "ContabeisDFCD",
        "ContabeisDFCI",
    )


@pytest.mark.parametrize(
    "payload",
    [
        [],
        {},
        {"value": ["invalid"]},
        {"value": [{"name": "Ativo", "url": None}]},
    ],
)
def test_service_document_shape_fails_closed(monkeypatch, payload) -> None:
    monkeypatch.setattr(
        SusepAccountingODataService,
        "_get_json",
        lambda *_args, **_kwargs: payload,
    )
    with pytest.raises((TypeError, ValueError)):
        SusepAccountingODataService().fetch_resource_names()


@pytest.mark.parametrize(
    "field, value, exception",
    [
        ("cnpj", None, TypeError),
        ("mesreferencia", None, TypeError),
        ("cmpid", None, TypeError),
        ("cmpid", 0, ValueError),
        ("valor", None, TypeError),
        ("valor", "nan", ValueError),
        ("cmptitulo", "", ValueError),
    ],
)
def test_accounting_row_invalid_values_fail_closed(field, value, exception) -> None:
    source = {
        "entnome": "SEGURADORA TESTE S.A.",
        "cnpj": "12345678000190",
        "mesreferencia": "2025-12-01",
        "cmpid": 518,
        "cmptitulo": "LUCRO LÍQUIDO / PREJUÍZO",
        "valor": "1.0",
    }
    source[field] = value
    with pytest.raises(exception):
        SusepAccountingODataService().parse_accounting_row(source)
