# Post-M20 — Historical model-route contract

Status: **implemented as an immutable fail-closed evidence contract; not yet integrated into historical readiness**.

## Objective

Represent an issuer's historical **project model family** directly for one fiscal year without pretending to reconstruct historical B3 sector/subsector/segment taxonomy.

`HistoricalModelRoute` answers only which project model family may be applied to one canonical CVM issuer/year based on evidence that was actually available by the simulated date.

## Identity, immutability and registry boundary

Every route uses the repository's canonical issuer identity exactly as:

```text
cvm:<CD_CVM>
```

The contract accepts only the literal ASCII form `^cvm:[1-9][0-9]*$`. Leading/trailing whitespace, uppercase prefixes, leading zeros, Unicode digit variants and arbitrary identifiers are rejected rather than normalized silently. Registry lookups enforce the same rule.

Validated routes are frozen Pydantic models. Changed copies through `model_copy(update=...)` are explicitly forbidden; changing evidence, eligibility, identity or availability requires constructing a new validated route. At registry ingestion, every route is reconstructed from plain dumped field data and validated again, so unchecked instances created through validation-bypassing APIs cannot carry structurally invalid state across the registry boundary.

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

The FCA source audit identified `Setor_Atividade`, `Descricao_Atividade` and receipt timing for the bounded 2024/2025 sample. The FCA filing ledger now binds those values to exact document/version receipt dates while validating issuer identity and reference period.

The current sector registry maps the bounded FCA values prospectively as:

- `Bancos` → `banks`;
- `Petróleo e Gás` → `commodities`;
- `Extração Mineral` → `commodities`.

A separate versioned mapping block must validate these FCA labels against the project registry before real routes are materialized. Unknown FCA labels must abstain; the `general_corporate` registry default must not become an implicit historical inference.

## Next integration step

The fundamental coverage profiler must consume an admissible historical route **before choosing the accounting contract**, because `banks`, `insurance` and `general_corporate` require different evidence. Company-years without a proven route must abstain rather than inherit today's B3 classification.

Until route generation and profiler/readiness integration are validated, `SECTOR_ROUTING_NOT_POINT_IN_TIME` remains active.
