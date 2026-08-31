import pandas as pd
import pytest

from ultimate_stock_analyzer.collectors.susep_field_dictionary import (
    profitability_field_candidate_evidence,
    profitability_field_evidence,
)


def test_profitability_field_evidence_uses_literal_normalized_terms() -> None:
    table = pd.DataFrame(
        [
            {
                "nuitem": 100,
                "noitem": "ATIVO TOTAL",
                "nuquad": "22A",
                "mercado": "S",
                "inivigencia": "201401",
                "fimvigencia": "210001",
            },
            {
                "nuitem": 200,
                "noitem": "LUCRO LÍQUIDO DO EXERCÍCIO",
                "nuquad": "23",
                "mercado": "S",
                "inivigencia": "201401",
                "fimvigencia": "210001",
            },
            {
                "nuitem": 300,
                "noitem": "RESULTADO DO EXERCÍCIO",
                "nuquad": "23",
                "mercado": "S",
                "inivigencia": "201401",
                "fimvigencia": "210001",
            },
            {
                "nuitem": 400,
                "noitem": "ATIVOS INTANGÍVEIS",
                "nuquad": "22A",
                "mercado": "S",
                "inivigencia": "201401",
                "fimvigencia": "210001",
            },
        ]
    )

    manifest = profitability_field_evidence(table)

    assert manifest["semantics_promoted"] is False
    assert manifest["matching_mode"] == "literal_case_and_accent_normalized_substring"
    fields = manifest["fields"]
    assert fields["ATIVO TOTAL"]["rows"][0]["nuitem"] == "100"
    assert fields["LUCRO LIQUIDO"]["rows"][0]["nuitem"] == "200"
    assert fields["RESULTADO DO EXERCICIO"]["rows"][0]["nuitem"] == "300"
    assert all(
        row["nuitem"] != "400"
        for evidence in fields.values()
        for row in evidence["rows"]
    )


def test_profitability_candidate_evidence_filters_exact_ids() -> None:
    table = pd.DataFrame(
        [
            {
                "nuitem": 518,
                "noitem": "LUCRO LIQUIDO",
                "nuquad": "23",
                "mercado": "S",
                "inivigencia": "200301",
                "fimvigencia": "210001",
            },
            {
                "nuitem": 1039,
                "noitem": "TOTAL DO ATIVO",
                "nuquad": "22A",
                "mercado": "S",
                "inivigencia": "200301",
                "fimvigencia": "210001",
            },
            {
                "nuitem": 3333,
                "noitem": "PATRIMONIO LIQUIDO",
                "nuquad": "22P",
                "mercado": "S",
                "inivigencia": "200301",
                "fimvigencia": "210001",
            },
            {
                "nuitem": 5035,
                "noitem": "PATRIMONIO LIQUIDO",
                "nuquad": "28",
                "mercado": "S",
                "inivigencia": "200301",
                "fimvigencia": "210001",
            },
            {
                "nuitem": 9999,
                "noitem": "UNRELATED",
                "nuquad": "99",
                "mercado": "S",
                "inivigencia": "200301",
                "fimvigencia": "210001",
            },
        ]
    )

    manifest = profitability_field_candidate_evidence(table)

    assert manifest["semantics_promoted"] is False
    assert manifest["candidate_ids"] == [518, 1039, 3333, 5035]
    assert set(manifest["fields"]) == {"518", "1039", "3333", "5035"}
    assert manifest["fields"]["518"]["rows"][0]["noitem"] == "LUCRO LIQUIDO"
    assert "9999" not in manifest["fields"]


def test_profitability_field_evidence_requires_exact_dictionary_schema() -> None:
    table = pd.DataFrame([{"nuitem": 100, "noitem": "ATIVO TOTAL"}])

    with pytest.raises(ValueError, match="nuquad"):
        profitability_field_evidence(table)
