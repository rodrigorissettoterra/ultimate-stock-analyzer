# Post-M20 — Historical model-route contract

Status: **implemented as a fail-closed evidence contract; not integrated into historical readiness yet**.

## Objective

Represent an issuer's historical **project model family** directly for one fiscal year without
pretending to reconstruct historical B3 sector/subsector/segment taxonomy.

`HistoricalModelRoute` is deliberately narrower than `SectorClassificationRecord`. It answers only:

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

`HistoricalModelRouteRegistry` performs exact company-year lookup and emits machine-readable blockers:

```text
HISTORICAL_MODEL_ROUTE_MISSING
HISTORICAL_MODEL_ROUTE_NOT_POINT_IN_TIME
HISTORICAL_MODEL_ROUTE_NOT_YET_AVAILABLE
```

There is intentionally **no fallback to the current B3 classification**. A 2024 route cannot spill
into 2025, and evidence cannot be consumed before `available_from`.

Diagnostic callers may explicitly set `require_point_in_time=false`, but that does not mutate the
route, promote readiness or authorize strict M15/M16 execution.

## Relationship to the FRE audit

The FRE source audit is a discovery step. If it later proves usable activity semantics, filing
timing and a deterministic mapping rule, those facts can materialize `HistoricalModelRoute` records.
The route contract itself does not assume FRE and can also accept another regulator/official source.

## Next integration step

The fundamental coverage profiler must eventually consume an explicit route **before choosing the
accounting contract**. That integration will be a separate gate because routing to `banks`,
`insurance` or `general_corporate` changes which fundamental fields are required.

Until that integration and complete route coverage are validated, `SECTOR_ROUTING_NOT_POINT_IN_TIME`
remains active.
