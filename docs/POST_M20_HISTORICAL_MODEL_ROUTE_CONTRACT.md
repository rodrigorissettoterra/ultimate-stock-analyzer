# Post-M20 — Historical model-route contract

Status: **implemented as an immutable fail-closed evidence contract; not yet integrated into historical readiness**.

## Objective

Represent an issuer's historical **project model family** directly for one fiscal year without pretending to reconstruct historical B3 sector/subsector/segment taxonomy.

`HistoricalModelRoute` answers only which project model family may be applied to one canonical CVM issuer/year based on evidence that was actually available by the simulated date.

## Identity and immutability

Every route uses the repository's canonical issuer identity exactly as:

```text
cvm:<CD_CVM>
```

Noncanonical spellings, leading-zero aliases and arbitrary identifiers are rejected rather than normalized silently. Registry lookups enforce the same rule.

Validated routes are frozen Pydantic models. Neither the caller, `routes()`, nor `decision.route` can mutate evidence identity, availability or `point_in_time_eligible` after registration. A changed evidence contract therefore requires constructing and validating a new route.

## Evidence contract

Each route binds:

- canonical `company_id` and exact `fiscal_year`;
- target project `model_id`;
- timezone-aware `available_from`;
- evidence source and source document;
- SHA-256 of the evidence artifact;
- explicit mapping-rule version;
- independent `point_in_time_eligible` status;
- optional human-readable reason.

A route never gains PIT status merely because it exists.

## Registry decisions

`HistoricalModelRouteRegistry` performs exact company-year lookup and emits:

```text
HISTORICAL_MODEL_ROUTE_MISSING
HISTORICAL_MODEL_ROUTE_NOT_POINT_IN_TIME
HISTORICAL_MODEL_ROUTE_NOT_YET_AVAILABLE
```

There is intentionally **no fallback to the current B3 classification**. Routes cannot spill into adjacent fiscal years or be consumed before `available_from`.

Strict PIT decisions require an explicit timezone-aware `as_of`. Omitting `as_of` in strict mode is rejected, preventing callers from accidentally bypassing the availability test. Diagnostic callers may explicitly set `require_point_in_time=false`; that path does not promote readiness or mutate the route.

## Relationship to FCA

The FCA source audit has identified `Setor_Atividade`, `Descricao_Atividade` and receipt timing for the bounded 2024/2025 sample. The filing-ledger block binds those values to exact document/version receipt dates. Once that lineage contract is finalized, a separate versioned mapping block may materialize real immutable `HistoricalModelRoute` records.

The current sector registry already maps the bounded FCA values prospectively as:

- `Bancos` → `banks`;
- `Petróleo e Gás` → `commodities`;
- `Extração Mineral` → `commodities`.

That mapping must still be validated as an explicit FCA routing rule before real routes are promoted.

## Next integration step

The fundamental coverage profiler must consume an admissible historical route **before choosing the accounting contract**, because `banks`, `insurance` and `general_corporate` require different evidence. Company-years without an admissible route must abstain rather than inherit today's B3 classification.

Until route generation and profiler/readiness integration are validated, `SECTOR_ROUTING_NOT_POINT_IN_TIME` remains active.
