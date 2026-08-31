from __future__ import annotations

import pandas as pd

ACCOUNTING_FIELD_CANDIDATES = (542, 4069)
FIELD_DICTIONARY_COLUMNS = (
    "nuitem",
    "noitem",
    "nuquad",
    "mercado",
    "inivigencia",
    "fimvigencia",
)


def candidate_accounting_field_evidence(table: pd.DataFrame) -> dict[str, object]:
    """Return exact sanitized dictionary rows for candidate SUSEP accounting fields.

    Candidate IDs are discovery inputs only. This function records what the official
    ``Ses_campos.csv`` dictionary says about those exact IDs and never promotes their
    semantics into scoring by itself.
    """

    missing = [column for column in FIELD_DICTIONARY_COLUMNS if column not in table.columns]
    if missing:
        raise ValueError(
            "missing required SUSEP Ses_campos columns: " + ", ".join(missing)
        )

    item_ids = pd.to_numeric(table["nuitem"], errors="coerce")
    evidence: dict[str, object] = {}
    for candidate in ACCOUNTING_FIELD_CANDIDATES:
        selected = table.loc[item_ids == candidate, list(FIELD_DICTIONARY_COLUMNS)].copy()
        rows: list[dict[str, object]] = []
        for _, row in selected.iterrows():
            rows.append(
                {
                    column: None if pd.isna(row[column]) else str(row[column]).strip()
                    for column in FIELD_DICTIONARY_COLUMNS
                }
            )
        evidence[str(candidate)] = {
            "present": bool(rows),
            "rows": rows,
        }

    return {
        "source_table": "Ses_campos.csv",
        "candidate_ids": list(ACCOUNTING_FIELD_CANDIDATES),
        "semantics_promoted": False,
        "fields": evidence,
    }
