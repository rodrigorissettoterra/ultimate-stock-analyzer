# M1/M2 — CVM Universe and Point-in-Time Financial Pipeline

## Scope

This milestone establishes the canonical issuer/security master and the normalized accounting
observation layer used by all later fundamental models.

## Free official sources

1. **CVM company registry** (`cad_cia_aberta.csv`) for issuer identity and registration status.
2. **CVM FCA** for listed securities and trading codes.
3. **CVM DFP / ITR** for structured annual and interim financial statements.

The FCA and DFP/ITR archives retain document versions/re-presentations. The pipeline never treats
the latest file as if it had always existed.

## Identity model

- `company_id = cvm:<CD_CVM>` is the stable internal issuer key.
- CNPJ is retained as an external identifier.
- Ticker belongs to a `SecurityRecord`, not to the issuer.
- ISIN is retained when the FCA provides it.

This allows one issuer to have multiple securities and permits ticker changes without breaking
historical issuer identity.

## Point-in-time contract

Every normalized statement line retains:

- document type (DFP/ITR);
- statement and consolidation scope;
- reference period;
- CVM document id when it can be attributed safely;
- document version;
- CVM receipt timestamp (`DT_RECEB`) when it can be attributed safely;
- `available_from`, equal to the evidenced receipt timestamp when attribution is unambiguous;
- collection timestamp;
- original source filename.

`point_in_time_lines(..., as_of=...)` excludes observations without an evidenced
`available_from` timestamp and selects only the latest revision that was available at the cutoff.

### Ambiguous filing metadata

CVM statement members normally do not expose `ID_DOC`, so DFP/ITR publication metadata can require
a fallback join on `CD_CVM + DT_REFER + VERSAO`. That natural key is not universally unique. If
multiple official documents share the key, metadata is collapsed only by field-level consensus.
A conflicting `DT_RECEB` suppresses all fallback document metadata for that key rather than
choosing the earliest or latest filing. Those statement rows remain usable for non-PIT analysis
but stay ineligible for PIT snapshots until publication lineage can be evidenced. A direct join on
an explicit `ID_DOC` remains strict and rejects conflicting metadata for the same document id.
Exact-issuer contract loaders use strict natural-key mode as well, so an issuer-specific accounting
audit still rejects unresolved filing lineage rather than silently degrading its evidence.

The market-wide behavior is intentionally granular: one ambiguous filing does not invalidate
unrelated, unambiguous statement rows in the same annual archive.

## Monetary scale

CVM statement values are normalized to BRL while preserving the source scale. Values marked
`MIL` are multiplied by 1,000 and values marked as millions by 1,000,000. Unknown scale labels
are preserved and treated as unit scale rather than guessed.

## Data lake policy

Raw CVM archives and normalized bulk data remain outside Git. The repository contains collectors,
normalizers, schemas and synthetic tests only.
