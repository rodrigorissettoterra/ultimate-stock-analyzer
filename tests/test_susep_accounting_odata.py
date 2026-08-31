from datetime import date
from decimal import Decimal

import pytest

from ultimate_stock_analyzer.collectors.susep_accounting_odata import (
    VERIFIED_ACCOUNTING_RESOURCES,
    SusepAccountingODataService,
)


def _accounting_row() -> dict[str, object]:
    return {
        "entnome": "SEGURADORA TESTE S.A.",
        "cnpj": "12.345.678/0001-90",
        "mesreferencia": "2025-12-01T00:00:00",
        "cmpid": 518,
        "cmptitulo": "(=) LUCRO LÍQUIDO / PREJUÍZO",
        "valor": "1234567.89",
        "cmpnumero": 99,
    }


def test_accounting_row_parses_documented_fields() -> None:
    row = SusepAccountingODataService().parse_accounting_row(_accounting_row())
    assert row.cnpj == "12345678000190"
    assert row.reference_month == date(2025, 12, 1)
    assert row.cmpid == 518
    assert row.value == Decimal("1234567.89")
    assert row.point_in_time_eligible is False


def test_accounting_row_accepts_negative_value() -> None:
    source = _accounting_row()
    source["valor"] = -50
    row = SusepAccountingODataService().parse_accounting_row(source)
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


def test_conflicting_resource_urls_fail_closed(monkeypatch) -> None:
    monkeypatch.setattr(
        SusepAccountingODataService,
        "_get_json",
        lambda *_args, **_kwargs: {
            "value": [
                {"name": "DRE", "url": "DRE"},
                {"name": "DRE", "url": "Other"},
            ]
        },
    )
    with pytest.raises(ValueError, match="conflicting"):
        SusepAccountingODataService().fetch_resource_catalog()


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


def test_metadata_extracts_function_and_function_import(monkeypatch) -> None:
    metadata = """<?xml version='1.0' encoding='utf-8'?>
    <edmx:Edmx xmlns:edmx='http://docs.oasis-open.org/odata/ns/edmx'
               xmlns='http://docs.oasis-open.org/odata/ns/edm'>
      <edmx:DataServices>
        <Schema Namespace='SUSEP'>
          <Function Name='ContabeisDRE'>
            <Parameter Name='Ano' Type='Edm.String' Nullable='false'/>
            <ReturnType Type='Collection(SUSEP.Row)'/>
          </Function>
          <EntityContainer Name='Container'>
            <FunctionImport Name='ContabeisDRE' Function='SUSEP.ContabeisDRE'/>
          </EntityContainer>
        </Schema>
      </edmx:DataServices>
    </edmx:Edmx>"""
    monkeypatch.setattr(
        SusepAccountingODataService,
        "_get_text",
        lambda *_args, **_kwargs: metadata,
    )
    catalog = SusepAccountingODataService().fetch_callable_catalog()
    assert len(catalog) == 2
    function = next(item for item in catalog if item.kind == "Function")
    function_import = next(item for item in catalog if item.kind == "FunctionImport")
    assert function.name == "ContabeisDRE"
    assert function.return_type == "Collection(SUSEP.Row)"
    assert function.parameters[0].name == "Ano"
    assert function.parameters[0].type_name == "Edm.String"
    assert function.parameters[0].nullable == "false"
    assert function_import.target == "SUSEP.ContabeisDRE"


def test_invalid_metadata_fails_closed(monkeypatch) -> None:
    monkeypatch.setattr(
        SusepAccountingODataService,
        "_get_text",
        lambda *_args, **_kwargs: "not xml",
    )
    with pytest.raises(ValueError, match="metadata XML"):
        SusepAccountingODataService().fetch_callable_catalog()


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
    source = _accounting_row()
    source[field] = value
    with pytest.raises(exception):
        SusepAccountingODataService().parse_accounting_row(source)
