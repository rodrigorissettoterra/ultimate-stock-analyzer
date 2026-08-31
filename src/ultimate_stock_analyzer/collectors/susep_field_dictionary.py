from __future__ import annotations

import unicodedata

import pandas as pd

ACCOUNTING_FIELD_CANDIDATES = (542, 4069)
PROFITABILITY_FIELD_TERMS = (
    "ATIVO TOTAL",
    "LUCRO LIQUIDO",
    "RESULTADO DO EXERCICIO",
)
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

    _require_dictionary_columns(table)

    item_ids = pd.to_numeric(table["nuitem"], errors="coerce")
    evidence: dict[str, object] = {}
    for candidate in ACCOUNTING_FIELD_CANDIDATES:
        selected = table.loc[item_ids == candidate, list(FIELD_DICTIONARY_COLUMNS)].copy()
        rows = _sanitized_rows(selected)
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


def profitability_field_evidence(table: pd.DataFrame) -> dict[str, object]:
    """Discover exact official dictionary descriptions relevant to insurer profitability.

    Search terms are fixed literal phrases after case/accent normalization. This is not
    fuzzy matching and does not infer a score-facing semantic contract. The output is a
    sanitized evidence manifest only; any field must be independently reviewed before
    it can be promoted into ROE/ROA calculations.
    """

    _require_dictionary_columns(table)
    normalized_descriptions = table["noitem"].map(_normalize_text)
    evidence: dict[str, object] = {}
    for term in PROFITABILITY_FIELD_TERMS:
        normalized_term = _normalize_text(term)
        selected = table.loc[
            normalized_descriptions.str.contains(normalized_term, regex=False, na=False),
            list(FIELD_DICTIONARY_COLUMNS),
        ].copy()
        rows = _sanitized_rows(selected)
        evidence[term] = {
            "present": bool(rows),
            "rows": rows,
        }

    return {
        "source_table": "Ses_campos.csv",
        "search_terms": list(PROFITABILITY_FIELD_TERMS),
        "matching_mode": "literal_case_and_accent_normalized_substring",
        "semantics_promoted": False,
        "fields": evidence,
    }


def _require_dictionary_columns(table: pd.DataFrame) -> None:
    missing = [column for column in FIELD_DICTIONARY_COLUMNS if column not in table.columns]
    if missing:
        raise ValueError(
            "missing required SUSEP Ses_campos columns: " + ", ".join(missing)
        )


def _sanitized_rows(table: pd.DataFrame) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for _, row in table.iterrows():
        rows.append(
            {
                column: None if pd.isna(row[column]) else str(row[column]).strip()
                for column in FIELD_DICTIONARY_COLUMNS
            }
        )
    return rows


def _normalize_text(value: object) -> str:
    if value is None or pd.isna(value):
        return ""
    text = unicodedata.normalize("NFKD", str(value))
    return "".join(character for character in text if not unicodedata.combining(character)).upper().strip()
