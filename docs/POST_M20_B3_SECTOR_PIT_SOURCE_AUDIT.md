# Post-M20 B3 Sector Point-in-Time Source Audit

## Decision

The public B3 industry-classification workbook is a current weekly snapshot. It can start an immutable
snapshot lineage from the moment it is collected, but it cannot be retrojected into 2024–2025 sector
routing.

This block is diagnostic only. `SECTOR_ROUTING_NOT_POINT_IN_TIME` remains unchanged. No sector model,
routing decision, score, weight, rankability, return, portfolio, historical readiness or walk-forward
readiness changes.

## Official source contract

The [B3 classification page](https://www.b3.com.br/pt_br/produtos-e-servicos/negociacao/renda-variavel/acoes/consultas/classificacao-setorial/)
states that its consultation base is updated weekly on the last business day during overnight
processing. The public download request contains only the language and returns the current workbook.

B3 also states that classifications are periodically reviewed when the products or services that drive
issuer revenue change. See the official
[classification criteria](https://www.b3.com.br/pt_br/produtos-e-servicos/negociacao/renda-variavel/acoes/consultas/criterio-de-classificacao/).
This makes historical version boundaries economically relevant rather than cosmetic.

## Workbook provenance audit

The live audit records:

- collection timestamp;
- SHA-256 and byte size of the downloaded XLSX;
- workbook member list and classification row count;
- presence or absence of Office core properties;
- date-like literals embedded in workbook metadata, shared strings and worksheet XML, including inline strings;
- requested historical years and the number actually covered by immutable historical snapshots.

An arbitrary date literal is never promoted to an as-of date. It would need an explicit B3 contract
that defines its temporal meaning. The current public workbook exposes no contractual historical as-of
parameter or immutable revision URLs.

## Fail-closed result

The audit always retains:

```text
B3_CLASSIFICATION_CURRENT_SNAPSHOT_ONLY
B3_CLASSIFICATION_AS_OF_CONTRACT_UNAVAILABLE
B3_CLASSIFICATION_REVISION_HISTORY_UNAVAILABLE
HISTORICAL_SECTOR_ROUTING_SOURCE_UNPROVEN
```

And therefore:

```text
contractual_as_of_date = null
historical_snapshot_count = 0
requested_years_covered = 0
historical_backfill_ready = false
sector_routing_point_in_time_ready = false
readiness_promotion_allowed = false
```

`current_snapshot_point_in_time_from_collection = true` has a narrow meaning: preserving the workbook,
hash and collection timestamp creates evidence for decisions made after that observation. It says
nothing about dates before collection.

## Why CVM FRE is not substituted

The official CVM FRE archives provide historical, structured issuer disclosures from 2010 onward,
including activities and several financial/corporate fields. They do not publish the B3
sector/subsector/segment decision or its effective dates. Reconstructing B3 taxonomy from free-form
business descriptions would create a new classifier and a new routing business rule, not recover the
historical B3 classification.

That alternative is therefore not silently used as historical ground truth.

## Live smoke

The workflow `b3-sector-pit-source-audit-smoke` downloads and parses the official current workbook,
then audits its ability to cover 2024–2025. It requires a non-empty classification, stable provenance
fields and all historical blockers. Any promotion of a current snapshot to historical PIT fails CI.

## Reproduction

```bash
python scripts/b3_sector_pit_source_audit.py \
  --start-year 2024 \
  --end-year 2025 \
  --output b3-sector-pit-source-audit.json
```
