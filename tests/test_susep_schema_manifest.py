import pandas as pd
import pytest

from scripts.susep_schema_manifest import _candidate_accounting_field_evidence


def test_candidate_accounting_field_evidence_is_exact_and_sanitized() -> None:
    table = pd.DataFrame(
        [
            {
                "nuitem": 542,
                "noitem": "Despesas Administrativas",
                "nuquad": "23",
                "mercado": "S",
                "inivigencia": "201312",
                "fimvigencia": None,
            },
            {
                "nuitem": 4069,
                "noitem": "Despesas Administrativas",
                "nuquad": "23P",
                "mercado": "P",
                "inivigencia": "201312",
                "fimvigencia": None,
            },
            {
                "nuitem": 9999,
                "noitem": "Unrelated",
                "nuquad": "99",
                "mercado": "S",
                "inivigencia": "201001",
                "fimvigencia": None,
            },
        ]
    )

    manifest = _candidate_accounting_field_evidence(table)

    assert manifest["semantics_promoted"] is False
    assert manifest["candidate_ids"] == [542, 4069]
    fields = manifest["fields"]
    assert fields["542"]["present"] is True
    assert fields["542"]["rows"][0]["noitem"] == "Despesas Administrativas"
    assert fields["4069"]["present"] is True
    assert "9999" not in fields


def test_candidate_accounting_field_evidence_requires_exact_dictionary_schema() -> None:
    table = pd.DataFrame([{"nuitem": 542, "noitem": "Despesas Administrativas"}])

    with pytest.raises(ValueError, match="nuquad"):
        _candidate_accounting_field_evidence(table)
