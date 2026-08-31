from scripts.b3_company_detail_schema_probe import (
    _detail_url,
    _flatten_scalars,
    _schema_paths,
    _semantic_scalars,
)


def test_detail_url_encodes_exact_cvm_code_payload() -> None:
    url = _detail_url("9512")
    assert url.startswith(
        "https://sistemaswebb3-listados.b3.com.br/"
        "listedCompaniesProxy/CompanyCall/GetDetail/"
    )
    assert "9512" not in url


def test_schema_probe_flattens_without_copying_whole_nested_response() -> None:
    payload = {
        "codeCVM": "9512",
        "companyName": "PETROLEO BRASILEIRO S.A.",
        "otherCodes": [
            {"code": "PETR3", "isin": "BRPETRACNOR9"},
            {"code": "PETR4", "isin": "BRPETRACNPR6"},
        ],
        "unrelated": {"value": "ignored by semantic selector"},
    }
    flattened = _flatten_scalars(payload)
    assert flattened["$.otherCodes[0].code"] == "PETR3"
    assert flattened["$.otherCodes[1].isin"] == "BRPETRACNPR6"

    semantic = _semantic_scalars(flattened)
    assert semantic["$.codeCVM"] == "9512"
    assert semantic["$.companyName"] == "PETROLEO BRASILEIRO S.A."
    assert semantic["$.otherCodes[0].code"] == "PETR3"
    assert "$.unrelated.value" not in semantic

    schema = _schema_paths(payload)
    assert schema["$"] == "dict"
    assert schema["$.otherCodes"] == "list"
    assert schema["$.otherCodes[0].code"] == "str"


def test_schema_probe_truncates_oversized_scalar_strings() -> None:
    flattened = _flatten_scalars({"companyName": "x" * 500})
    value = flattened["$.companyName"]
    assert isinstance(value, str)
    assert len(value) == 301
    assert value.endswith("…")
