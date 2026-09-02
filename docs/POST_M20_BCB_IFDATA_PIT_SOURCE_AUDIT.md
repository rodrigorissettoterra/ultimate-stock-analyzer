# Post-M20 BCB IFData Point-in-Time Source Audit

## Decision

The official BCB IFData source has a defensible **initial publication schedule**, but the public
OData contract does not provide the revision-aware historical replay required by a strict
point-in-time backtest.

This block is diagnostic only. `BANK_EVIDENCE_NOT_POINT_IN_TIME` remains active. No bank profile,
coverage rule, score, weight, rankability, return, portfolio, historical readiness or walk-forward
readiness changes.

## Official publication contract

The BCB open-data catalog and IFData methodology state that IFData reports are published
quarterly:

- 60 days after the March, June and September reference dates;
- 90 days after the December reference date.

For the periods used by the live audit this gives:

```text
2024-12-31 -> 2025-03-31
2025-06-30 -> 2025-08-29
2025-12-31 -> 2026-03-31
```

This is useful temporal evidence, but it answers only **when a period is first scheduled to become
public**. It does not identify which revision of a historical row was visible on an arbitrary later
simulated date.

## OData temporal boundary

The audit downloads the live IFData OData `$metadata` document and bounded samples from both
`IfDataCadastro` and report 1 (`IfDataValores`) for the requested periods. It preserves:

- metadata SHA-256 and byte size;
- exposed entity-property names;
- exposed function-parameter names;
- any metadata names that look revision/publication/version related;
- SHA-256, byte size, row count and observed fields for each live sample;
- collection timestamp.

`AnoMes` is treated as an accounting/reference period. It is not silently reinterpreted as an
`as-of` vintage selector.

Even if a future metadata field has a revision-like name, the audit will not promote it solely from
the name. Revision-aware replay requires an explicit semantic contract proving that the field or
parameter can reconstruct what was observable at the simulated date.

## Fail-closed result

The audit retains:

```text
BANK_EVIDENCE_NOT_POINT_IN_TIME
IFDATA_HISTORICAL_VINTAGE_QUERY_UNAVAILABLE
IFDATA_REVISION_HISTORY_UNAVAILABLE
IFDATA_ROW_PUBLICATION_TIMESTAMP_UNAVAILABLE
```

and therefore:

```text
initial_publication_timing_proven = true
row_level_publication_timestamp_proven = false
revision_history_proven = false
historical_vintage_query_proven = false
current_observation_point_in_time_from_collection = true
historical_replay_ready = false
bank_evidence_point_in_time_ready = false
readiness_promotion_allowed = false
```

`current_observation_point_in_time_from_collection = true` has a narrow meaning: preserving a raw
payload and its collection timestamp can start an immutable **forward** snapshot lineage. It does not
make a current observation of a 2024 or 2025 reference period safe to retroject into those years.

## Relationship to `available_from_estimate`

`BankPrudentialAnnualRecord.available_from_estimate` remains a conservative research field and is
not PIT authorization. The newly audited official release schedule can support a future explicit
initial-availability field, but that still would not solve revision contamination in a current API
observation.

Accordingly, this block does not change `point_in_time_eligible=false` on IFData bank profiles.

## Live smoke

The workflow `bcb-ifdata-pit-source-audit-smoke` inspects the official service for:

```text
202412
202506
202512
```

It requires non-empty live cadastro/report samples, stable provenance fields, the official 60/90-day
initial-release calculations and all fail-closed revision blockers. Any readiness promotion fails the
workflow.

## Reproduction

```bash
python scripts/bcb_ifdata_pit_source_audit.py \
  --periods 202412 202506 202512 \
  --output bcb-ifdata-pit-source-audit.json
```

## Official references

- BCB open-data dataset: `IFData - Dados selecionados de instituições financeiras`
- BCB IFData OData service: `https://olinda.bcb.gov.br/olinda/servico/IFDATA/versao/v1/odata`
- BCB `Esclarecimentos e Metodologia` for the quarterly publication delays and source scopes.
