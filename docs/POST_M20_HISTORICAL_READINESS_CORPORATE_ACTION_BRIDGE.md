# Post-M20 — Corporate-action evidence bridge into historical readiness

Status: **implemented as a fail-closed readiness attribution layer; no readiness or weight
promotion**.

## Objective

Connect the historical event-aware M15 integration evidence to the global M15/M16 readiness audit
without confusing two different claims:

1. the M15 return engine can consume validated corporate actions while preserving raw COTAHIST;
2. the available historical corporate-action evidence is complete for the exact backtest universe
   and date window.

The first claim is now demonstrable. The second remains source- and scope-dependent.

## Why the distinction matters

Raw B3 COTAHIST does not populate `adjusted_close`. That alone does not require manufacturing an
adjusted historical price series because M15 can process `ShareAction` and `CashDistribution` inputs
separately.

However, an event-aware return formula is safe for strict historical evaluation only when the event
ledger is sufficiently complete for the exact securities and period being simulated. A bounded smoke
sample cannot silently become evidence for another ticker or another date window.

## Readiness contract

`CorporateActionReadinessEvidence` records:

- the ticker and date scope of the event integration evidence;
- whether the bounded M15 event-aware path was actually exercised;
- whether raw prices were preserved;
- whether price adjustment was avoided;
- whether historical source completeness was proven;
- whether the event dataset itself is strict-backtest ready;
- the event-source blockers carried by the integration report;
- the SHA-256 fingerprint of the integration JSON used by the readiness run.

The global `HistoricalBacktestReadinessReport` now exposes:

- whether corporate-action evidence was attached;
- the evidence ticker/date scope;
- whether that scope covers the requested readiness universe;
- whether it covers the requested historical window;
- whether the M15 event-aware path was validated;
- whether historical event-source completeness was proven;
- the resulting corporate-action readiness blockers;
- the active price-treatment mode.

## Price-treatment modes

The readiness audit distinguishes four states:

- `ADJUSTED_CLOSE`: every historical bar already has an adjusted close;
- `EVENT_AWARE_M15_STRICT`: raw prices are acceptable because strict, scope-matched event evidence
  is available and the validated M15 event path is applicable;
- `EVENT_AWARE_M15_DIAGNOSTIC_ONLY`: the M15 event-aware path is demonstrated, but source or scope
  blockers still prevent strict historical evaluation;
- `RAW_UNADJUSTED_UNRESOLVED`: no validated strict treatment exists for the raw price
  discontinuities.

## Fail-closed scope rules

Unadjusted COTAHIST can lose `PRICE_SERIES_UNADJUSTED_FOR_CORPORATE_ACTIONS` only if all of the
following are true:

1. the M15 event-aware path has been validated;
2. raw COTAHIST was preserved and not pre-adjusted;
3. historical corporate-action source completeness is proven;
4. the event dataset declares strict event-aware backtest readiness;
5. the event evidence covers every requested ticker;
6. the event evidence covers the complete requested date window;
7. no corporate-action readiness blocker remains.

If any condition fails, the global price blocker remains and the granular event blocker is added to
the readiness report.

Two scope-specific blockers are now explicit:

- `CORPORATE_ACTION_EVIDENCE_UNIVERSE_INCOMPLETE`;
- `CORPORATE_ACTION_EVIDENCE_WINDOW_INCOMPLETE`.

A missing integration proof is represented by `CORPORATE_ACTION_M15_PATH_UNVALIDATED` when event
evidence is supplied but does not actually demonstrate the M15 path.

## Live smoke behavior

The global historical-readiness smoke now creates a bounded event-aware M15 integration report using
the established MGLU3, ITSA4, B3SA3 and AMER3 2024–2025 regression sample, fingerprints that JSON,
and attaches it to the readiness audit.

The readiness universe remains PETR4, VALE3 and ITUB4. This mismatch is intentional: the smoke must
show that a valid M15 capability proof is visible while **not** being allowed to expand to
securities outside its evidence scope.

Therefore the current expected state is:

- M15 event-aware path validated: `true`;
- historical event-source completeness: still not proven;
- evidence universe matches readiness universe: `false`;
- price-treatment mode: `EVENT_AWARE_M15_DIAGNOSTIC_ONLY`;
- `PRICE_SERIES_UNADJUSTED_FOR_CORPORATE_ACTIONS`: retained;
- `CORPORATE_ACTION_EVIDENCE_UNIVERSE_INCOMPLETE`: retained;
- no M15/M16 readiness or weight promotion.

## Future promotion path

This bridge removes the need to require synthetic adjusted prices as the only possible resolution.
A future broad historical dataset can legitimately use raw COTAHIST plus separate corporate-action
inputs if a complete historical event contract is proven for the exact backtest scope.

Until then, the project has stronger evidence attribution but remains conservative by design.
