# Post-M20 — Historical model-route contract

Status: **implemented as a fail-closed evidence contract; not integrated into historical readiness yet**.

## Objective

Represent an issuer's historical **project model family** directly for one fiscal year without
pretending to reconstruct historical B3 sector/subsector/segment taxonomy.

`HistoricalModelRoute` answers only:

> Which project model family may be applied to this company-year, based on evidence that was
> actually available by the simulated date?

## Evidence contract

Each route binds:

- exact `company_id` and `fiscal_year`;
- target project `model_id`;
- timezone-aware `available_from`;
- evidence source and source document;
- SHA-256 of the evidence artifact;
- explicit mapping-rule version;
- independent `point_in_time_eligible` status;
- optional human-readable reason.

A route never gains PIT status merely because it exists.

## Registry decisions

`HistoricalModelRouteRegistry` performs exact company-year lookup and emits machine-readable
blockers when an explicit route is missing, non-PIT or not yet available:

```text
HISTORICAL_MODEL_ROUTE_MISSING
HISTORICAL_MODEL_ROUTE_NOT_POINT_IN_TIME
HISTORICAL_MODEL_ROUTE_NOT_YET_AVAILABLE
```

There is intentionally **no fallback to the current B3 classification**. A 2024 route cannot spill
into 2025, and evidence cannot be consumed before `available_from`.

Strict PIT decisions require an explicit timezone-aware `as_of`. Omitting `as_of` in strict mode is
rejected rather than silently skipping the availability test, preventing look-ahead leakage by API
misuse. Diagnostic callers may set `require_point_in_time=false`; that path can omit `as_of`, but it
does not mutate the route, promote readiness or authorize strict M15/M16 execution.

## Relationship to official-source audits

The route contract is source-agnostic. The FRE audit tests filing lineage but has not established a
usable structured applicability field. The FCA audit has identified promising `Setor_Atividade` and
`Descricao_Atividade` evidence plus receipt timing in the bounded 2024/2025 sample, but exact
per-filing semantic mapping must be validated before real routes are materialized.

## Next integration step

The next source block must bind FCA detail rows to their exact filing/version receipt timestamps and
validate a deterministic mapping rule. Only then may `HistoricalModelRoute` records be generated.

The fundamental coverage profiler must consume an admissible route **before choosing the accounting
contract**, because routing to `banks`, `insurance` or `general_corporate` changes which fundamental
fields are required.

Until route generation, coverage and profiler integration are validated,
`SECTOR_ROUTING_NOT_POINT_IN_TIME` remains active.
