# Post-M20 — Historical routes in fundamental coverage and readiness

## Goal

Use persisted `HistoricalModelRoute` evidence as the only sector/model-routing source when
fundamental coverage and M15/M16 readiness are evaluated for a historical `as_of`.

This block does not make the historical backtest fully ready. It removes the known dependency
on current B3 classification for historical accounting-model selection while preserving the
independent fail-closed blockers for specialized evidence, corporate actions, price treatment
and any remaining fundamental point-in-time gaps.

## Compatibility

`FundamentalCoverageProfiler.analyze()` and
`audit_historical_backtest_readiness()` keep their existing behavior when `as_of=None`.

Historical behavior is activated only by an explicit timezone-aware `as_of`.

## Historical routing contract

In historical mode:

- current B3 classification is never used as a fallback;
- routing is resolved from the persisted `HistoricalModelRouteRegistry`;
- missing, non-PIT and not-yet-available routes remain explicit blockers;
- the route model must exist in the supplied sector registry;
- `general_corporate`, `utilities` and `commodities` use the general CVM accounting contract;
- `banks` and `insurance` require specialized accounting treatment;
- abstention or unknown models are not silently coerced into `general_corporate`.

Coverage records preserve the route model, `available_from`, evidence source and source
document even when the decision is blocked.

## Fundamental `as_of` visibility

For general CVM financial statements, historical point-in-time coverage is recomputed from
only the statement rows whose timezone-aware `available_from` is visible at the requested
`as_of`.

The existing fixed-account extractor then chooses the highest document/version only among
those visible rows. A later restatement therefore cannot leak into an earlier decision date.

Coverage distinguishes:

- critical inputs that are structurally missing;
- critical inputs present without usable PIT timing;
- critical inputs whose only usable evidence becomes available after `as_of`.

Full-data coverage remains diagnostic, while point-in-time critical coverage is the strict
historical value.

Latest-state IFData bank evidence remains non-PIT until a revision-history contract proves
otherwise.

## Historical readiness contract

When `as_of` is supplied, readiness requires granular coverage records from the same
`as_of`. It reports:

- historical route company-years;
- admissible historical route company-years;
- granular route gaps with company, fiscal year, ticker, model and provenance;
- fundamental PIT gaps including not-yet-available critical inputs;
- a `current_b3_fallback_used=false` invariant.

Current B3 classification counts may remain visible as diagnostics, but they do not create or
clear historical route blockers.

## Live smoke

The historical-readiness smoke now:

1. bootstraps the bounded PETR4/VALE3/ITUB4 sample without current B3 classification;
2. persists historical FCA routes into the completed bootstrap run;
3. runs the fundamental profiler with an explicit historical `as_of`;
4. runs readiness with the same `as_of`;
5. requires zero historical route gaps and no `SECTOR_ROUTING_NOT_POINT_IN_TIME` blocker;
6. keeps independent blockers such as latest-state IFData and unadjusted prices fail-closed;
7. preserves the existing bounded corporate-action/M15 diagnostic evidence.

This is routing/readiness plumbing, not a scoring or weight-promotion change.
