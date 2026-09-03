# Post-M20 — CVM FCA applicability filing ledger

Status: **exact filing-lineage evidence contract; no model-route or readiness promotion**.

## Objective

Bind each observed structured FCA `geral` applicability row to the exact root FCA filing that establishes when that evidence became available.

The ledger is the temporal bridge between the FCA source audit and a later `HistoricalModelRoute` materializer. It does not itself decide a model family.

## Exact join contract

An applicability row is materialized only when the root filing matches all of:

- `ID_Documento` ↔ `ID_DOC`;
- `Versao` ↔ `VERSAO`;
- `Codigo_CVM` ↔ `CD_CVM`;
- normalized issuer CNPJ;
- `Data_Referencia` ↔ `DT_REFER`.

Missing, ambiguous, cross-issuer, cross-period or version-mismatched joins fail closed. The ledger also tracks the CVM codes actually observed in the detail member and emits `FCA_APPLICABILITY_DETAIL_NOT_FOUND` when **any** requested issuer lacks structured applicability detail.

## Point-in-time timing

The root FCA CSV exposes `DT_RECEB` as a date without intraday time. To avoid assuming same-day availability, the ledger uses:

```text
available_from = DT_RECEB + 1 calendar day at 00:00 UTC
```

Each observed detail revision is independently eligible only from its own `available_from`. Missing older revisions are never inferred from a later/current row.

## Evidence fingerprint

Each accepted filing receives a SHA-256 over normalized lineage including:

- archive SHA-256;
- CVM code and CNPJ;
- document ID and version;
- reference date and receipt date;
- `Setor_Atividade`;
- `Descricao_Atividade`.

The annual source URL, archive SHA-256 and archive size are retained separately.

## Live bounded evidence

The smoke validates the official 2024 and 2025 FCA archives for:

- Petrobras — CVM 9512 — `Petróleo e Gás`;
- Vale — CVM 4170 — `Extração Mineral`;
- Itaú Unibanco — CVM 19348 — `Bancos`.

The live gate requires all three issuers to have detail evidence in each audited archive and requires every selected detail row to materialize through the exact join contract.

## Safety boundary

This ledger does **not**:

- infer historical B3 taxonomy;
- fill missing issuer/revision evidence;
- choose a project model family;
- remove `SECTOR_ROUTING_NOT_POINT_IN_TIME`;
- promote historical readiness or M16 weights.

The next block may map accepted FCA sector evidence through an explicit, versioned project mapping rule and then construct immutable `HistoricalModelRoute` records.
