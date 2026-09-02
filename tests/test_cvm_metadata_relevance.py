import warnings

import pandas as pd

from ultimate_stock_analyzer.normalization.cvm import attach_document_metadata


def test_natural_key_join_ignores_unrelated_ambiguous_metadata() -> None:
    statement = pd.DataFrame(
        [{"CD_CVM": 12345, "DT_REFER": "2025-12-31", "VERSAO": 1}]
    )
    metadata = pd.DataFrame(
        [
            {
                "CD_CVM": 12345,
                "DT_REFER": "2025-12-31",
                "VERSAO": 1,
                "ID_DOC": 100,
                "DT_RECEB": "2026-03-01",
            },
            {
                "CD_CVM": 99999,
                "DT_REFER": "2025-12-31",
                "VERSAO": 1,
                "ID_DOC": 200,
                "DT_RECEB": "2026-03-02",
            },
            {
                "CD_CVM": 99999,
                "DT_REFER": "2025-12-31",
                "VERSAO": 1,
                "ID_DOC": 201,
                "DT_RECEB": "2026-04-02",
            },
        ]
    )

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", RuntimeWarning)
        joined = attach_document_metadata(statement, metadata)

    assert caught == []
    assert joined.loc[0, "ID_DOC"] == 100
    assert joined.loc[0, "DT_RECEB"] == "2026-03-01"
