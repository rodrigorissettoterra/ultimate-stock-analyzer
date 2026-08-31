from datetime import date
from decimal import Decimal

import pytest

from ultimate_stock_analyzer.collectors.susep_provisions_odata import (
    SusepProvisionsODataService,
)


def _row() -> dict[str, object]:
    return {
        "entnome": "SEGURADORA TESTE S.A.",
        "cnpj": "12.345.678/0001-90",
        "mesreferencia": "2025-12-01T00:00:00",
        "grupo": "01",
        "ramo": "0111",
        "provisao": "PROVISÃO TESTE",
        "valor": "100.25",
    }


def test_provision_row_parses_documented_insurance_fields() -> None:
    row = SusepProvisionsODataService().parse_provision_row(_row())
    assert row.cnpj == "12345678000190"
    assert row.reference_month == date(2025, 12, 1)
    assert row.provision == "PROVISÃO TESTE"
    assert row.value == Decimal("100.25")
    assert row.group == "01"
    assert row.branch == "0111"
    assert row.point_in_time_eligible is False


def test_provision_row_supports_resources_without_group_and_branch() -> None:
    source = _row()
    source.pop("grupo")
    source.pop("ramo")
    row = SusepProvisionsODataService().parse_provision_row(source)
    assert row.group is None
    assert row.branch is None


def test_negative_provision_value_is_preserved_as_source_evidence() -> None:
    source = _row()
    source["valor"] = -1
    assert SusepProvisionsODataService().parse_provision_row(source).value == Decimal(-1)


def test_resource_catalog_is_exact_sorted_and_deduplicated(monkeypatch) -> None:
    monkeypatch.setattr(
        SusepProvisionsODataService,
        "_get_json",
        lambda *_args, **_kwargs: {
            "value": [
                {"name": "Seguros", "url": "Seguros"},
                {"name": "Previdencia", "url": "Previdencia"},
                {"name": "Seguros", "url": "Seguros"},
            ]
        },
    )
    catalog = SusepProvisionsODataService().fetch_resource_catalog()
    assert [(item.name, item.url) for item in catalog] == [
        ("Previdencia", "Previdencia"),
        ("Seguros", "Seguros"),
    ]


def test_conflicting_resource_urls_fail_closed(monkeypatch) -> None:
    monkeypatch.setattr(
        SusepProvisionsODataService,
        "_get_json",
        lambda *_args, **_kwargs: {
            "value": [
                {"name": "Seguros", "url": "Seguros"},
                {"name": "Seguros", "url": "Other"},
            ]
        },
    )
    with pytest.raises(ValueError, match="conflicting"):
        SusepProvisionsODataService().fetch_resource_catalog()


@pytest.mark.parametrize(
    "field, value, exception",
    [
        ("cnpj", None, TypeError),
        ("mesreferencia", None, TypeError),
        ("provisao", "", ValueError),
        ("valor", None, TypeError),
        ("valor", "nan", ValueError),
        ("grupo", 1, TypeError),
        ("ramo", 1, TypeError),
    ],
)
def test_invalid_provision_rows_fail_closed(field, value, exception) -> None:
    source = _row()
    source[field] = value
    with pytest.raises(exception):
        SusepProvisionsODataService().parse_provision_row(source)
