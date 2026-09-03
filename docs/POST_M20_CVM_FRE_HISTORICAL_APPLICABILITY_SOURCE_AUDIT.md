# Post-M20 — CVM FRE historical model-applicability source audit

Status: **diagnostic source audit; no sector-routing or readiness promotion**.

## Objective

Inspect official historical CVM Formulário de Referência (FRE) structured archives for evidence that
could support historical project model-family applicability, without reconstructing or backfilling
B3 taxonomy.

## Identity propagation across detail members

FRE detail CSVs do not necessarily repeat `CD_CVM`. The audit therefore first builds bounded issuer
identity maps from any rows that carry the requested CVM codes and propagates identity through:

- CNPJ (`CNPJ_CIA`, `CNPJ_Companhia` or equivalent);
- filing document identity (`ID_DOC`, `ID_Documento` or equivalent).

Only then are activity-like fields and values inspected. This prevents a detail member from being
silently discarded merely because it lacks `CD_CVM`.

## Evidence categories

The audit keeps four categories separate:

- activity/business candidates;
- actual receipt/delivery/publication timing candidates;
- reporting/reference-period metadata such as `DT_REFER`;
- revision/version metadata.

Reference dates and version numbers never count as publication timing.

## Bounded live contract

The smoke inspects delivery-year archives 2024 and 2025 for Petrobras (9512), Vale (4170) and Itaú
Unibanco (19348). A green run now requires, for **both** archives:

- complete bounded issuer coverage;
- a real receipt/delivery/publication-like timing field with values;
- a valid archive SHA-256 and nonempty CSV inventory;
- no routing/readiness promotion.

This means parser regressions or upstream schema changes that make the requested issuers disappear
cannot remain green simply because the audit is fail-closed.

## Fail-closed boundary

Candidate activity fields are discovery evidence only. Even if activity values are found after the
identity join, mapping their semantics to `banks`, `insurance`, `commodities`, `utilities` or another
project model requires a separate versioned rule.

Core blockers include:

```text
FRE_STRUCTURED_ACTIVITY_FIELD_UNAVAILABLE
FRE_ISSUER_COVERAGE_INCOMPLETE
FRE_FILING_TIMING_FIELDS_UNPROVEN
FRE_ACTIVITY_TO_MODEL_MAPPING_UNPROVEN
HISTORICAL_MODEL_APPLICABILITY_UNPROVEN
```

`FRE_ACTIVITY_TO_MODEL_MAPPING_UNPROVEN` and `HISTORICAL_MODEL_APPLICABILITY_UNPROVEN` remain active
throughout this source-audit block.

## Relationship to FCA

The parallel FCA audit already proved a stronger structured source for the bounded sample:
`Setor_Atividade`, `Descricao_Atividade` and root `DT_RECEB` are directly available. FCA is therefore
the leading source for historical route construction. This corrected FRE audit remains valuable as a
properly grounded source assessment and as potential corroborating evidence; it is no longer allowed
to reach a negative conclusion by ignoring detail-member identity.
