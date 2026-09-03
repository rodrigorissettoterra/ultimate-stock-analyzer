# Post-M20 — CVM FCA applicability filing ledger

Status: **exact filing-lineage adapter; no historical model-route/readiness promotion**.

## Objective

Convert the promising FCA source discovery into temporally usable evidence by binding each
structured applicability row to the exact FCA root filing that supplied its receipt date.

The source audit proved that `fca_cia_aberta_geral` exposes `Setor_Atividade` and
`Descricao_Atividade`, while the root `fca_cia_aberta_<year>.csv` exposes `ID_DOC`, `VERSAO` and
`DT_RECEB`. The ledger joins those two contracts rather than assigning a generic archive-level date.

## Exact join contract

For each requested issuer detail row:

1. `ID_Documento` must identify exactly one root `ID_DOC`;
2. detail `Versao` must equal root `VERSAO`;
3. the root must expose `DT_RECEB`;
4. the detail must expose `Setor_Atividade`;
5. issuer identity remains explicit through CVM code/CNPJ;
6. the evidence fingerprint includes archive SHA-256, document/version identity, reference date,
   receipt date, sector and activity description.

Ambiguous, missing or version-mismatched joins fail closed.

## Conservative publication timing

The public FCA CSV exposes a receipt **date**, not an intraday timestamp. The ledger therefore sets:

```text
available_from = DT_RECEB + 1 calendar day at 00:00 UTC
```

This mirrors the project's conservative CVM date-only availability policy and prevents using a filing
on the same calendar date when the exact publication time is unknown.

## Revision boundary

The current annual archive can contain multiple root filing versions while a structured detail member
may expose only the revisions currently represented there. The ledger does **not** infer missing older
detail content.

This does not make an observed detail revision unusable. A materialized filing is independently PIT
eligible **only from its own `available_from` onward**. A strict historical request earlier than that
must use another explicitly observed revision or abstain.

## Bounded live gate

The live smoke checks FCA 2024 and 2025 for Petrobras (9512), Vale (4170) and Itaú Unibanco (19348).
It requires every bounded applicability detail row to join exactly and expects the source sectors
already observed by the preceding audit:

- `Petróleo e Gás`;
- `Extração Mineral`;
- `Bancos`.

The workflow publishes document IDs, versions, receipt dates, conservative availability timestamps
and evidence hashes, but still keeps `readiness_promotion_allowed=false`.

## Next step

Once this ledger is green, a separate versioned mapping block can apply the project's existing sector
registry to `Setor_Atividade`. In the current registry, the bounded values prospectively resolve to
`commodities`, `commodities` and `banks`, respectively. That mapping must be tested and recorded as an
explicit rule before `HistoricalModelRoute` records are generated.
