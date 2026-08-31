import pytest

from ultimate_stock_analyzer.collectors.susep_identity import (
    SusepLicensedEntityRecord,
    SusepOlindaIdentityCollector,
    match_susep_entities_by_cnpj,
    matched_susep_fip_codes,
    normalize_cnpj,
    normalize_fip_code,
)


def _record(*, cnpj: str, fip_code: str, name: str = "SEGURADORA TESTE S.A."):
    return SusepLicensedEntityRecord(legal_name=name, cnpj=cnpj, fip_code=fip_code)


def test_cnpj_normalization_accepts_official_formatting() -> None:
    assert normalize_cnpj("12.345.678/0001-90") == "12345678000190"
    assert normalize_cnpj("12345678000190") == "12345678000190"


def test_fip_code_preserves_leading_zeroes() -> None:
    assert normalize_fip_code("06947") == "06947"


def test_exact_cnpj_match_ignores_names_and_nonmatching_entities() -> None:
    records = [
        _record(cnpj="12.345.678/0001-90", fip_code="06947", name="ALFA SEGURADORA"),
        _record(cnpj="98.765.432/0001-10", fip_code="01234", name="ALFA SEGURADORA"),
        _record(cnpj="12.345.678/0001-91", fip_code="05678", name="ALFA SEGURADORA S.A."),
    ]
    matches = match_susep_entities_by_cnpj("12345678000190", records)
    assert len(matches) == 1
    assert matches[0].normalized_fip_code == "06947"


def test_multiple_exact_registry_matches_are_preserved_and_deterministic() -> None:
    records = [
        _record(cnpj="12.345.678/0001-90", fip_code="09999", name="B"),
        _record(cnpj="12.345.678/0001-90", fip_code="01111", name="A"),
    ]
    assert matched_susep_fip_codes("12.345.678/0001-90", records) == ("01111", "09999")


def test_duplicate_same_cnpj_and_fip_is_deduplicated() -> None:
    records = [
        _record(cnpj="12.345.678/0001-90", fip_code="06947", name="NAME A"),
        _record(cnpj="12345678000190", fip_code="06947", name="NAME B"),
    ]
    matches = match_susep_entities_by_cnpj("12345678000190", records)
    assert len(matches) == 1
    assert matches[0].normalized_fip_code == "06947"


def test_olinda_row_uses_documented_identity_fields() -> None:
    collector = SusepOlindaIdentityCollector()
    record = collector._parse_row(
        {
            "mercodigo": 2,
            "entcodigofip": "06947",
            "entnome": "UNIMED SEGURADORA S.A.",
            "entcgc": "92.863.505/0001-06",
        }
    )
    assert record.legal_name == "UNIMED SEGURADORA S.A."
    assert record.cnpj == "92863505000106"
    assert record.fip_code == "06947"
    assert record.entity_type == "2"
    assert record.source == "SUSEP_OLINDA_EMPRESAS"


def test_olinda_response_shape_fails_closed() -> None:
    collector = SusepOlindaIdentityCollector()
    with pytest.raises(TypeError, match="response shape"):
        collector._response_rows([])
    with pytest.raises(TypeError, match="response shape"):
        collector._response_rows({"records": []})
    with pytest.raises(TypeError, match="row shape"):
        collector._response_rows({"value": ["invalid"]})


@pytest.mark.parametrize(
    "row, exception, message",
    [
        (
            {"mercodigo": 2, "entcodigofip": "06947", "entnome": "", "entcgc": "92863505000106"},
            ValueError,
            "legal name",
        ),
        (
            {"mercodigo": 2, "entcodigofip": "06947", "entnome": "A", "entcgc": None},
            TypeError,
            "CNPJ",
        ),
        (
            {"mercodigo": 2, "entcodigofip": None, "entnome": "A", "entcgc": "92863505000106"},
            TypeError,
            "FIP code",
        ),
    ],
)
def test_olinda_invalid_identity_rows_fail_closed(
    row: dict, exception: type[Exception], message: str
) -> None:
    with pytest.raises(exception, match=message):
        SusepOlindaIdentityCollector()._parse_row(row)


@pytest.mark.parametrize("value", ["", "123", "12.345.678/0001", "ABC"])
def test_invalid_cnpj_fails_closed(value: str) -> None:
    with pytest.raises(ValueError, match="14 digits"):
        normalize_cnpj(value)


@pytest.mark.parametrize("value", ["", "ABC", "06-947"])
def test_invalid_fip_code_fails_closed(value: str) -> None:
    with pytest.raises(ValueError, match="only digits"):
        normalize_fip_code(value)
