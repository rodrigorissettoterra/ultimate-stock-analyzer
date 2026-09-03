# Post-M20 — Corporate-action evidence bridge into historical readiness

Status: **fail-closed readiness attribution; no readiness or weight promotion**.

## Objective

Connect the historical event-aware M15 integration evidence to the global M15/M16 readiness
audit without conflating engine capability, event-source completeness, evidence scope or raw-price
provenance.

Raw B3 COTAHIST remains immutable. M15 may consume `ShareAction` and `CashDistribution` objects
separately, so strict historical evaluation does not require manufacturing `adjusted_close`.

## Strict contract

Unadjusted COTAHIST can lose `PRICE_SERIES_UNADJUSTED_FOR_CORPORATE_ACTIONS` only when all of the
following are true:

1. the M15 event-aware path was actually exercised;
2. raw COTAHIST was preserved and not pre-adjusted;
3. historical corporate-action source completeness is proven;
4. the event dataset declares strict event-aware readiness;
5. the evidence covers every requested ticker;
6. the evidence covers the complete requested date window;
7. the event evidence raw-price SHA-256 matches the exact COTAHIST bars in the audited bootstrap;
8. no corporate-action readiness blocker remains.

The seventh condition binds the event evidence to the same market-data artifacts being certified.
A report generated from another COTAHIST download cannot unlock the readiness result merely because
its tickers and years happen to match.

## Reported provenance

`CorporateActionReadinessEvidence` retains:

- event-evidence ticker/date scope;
- the event dataset `raw_price_fingerprint_sha256`;
- whether the M15 path was demonstrated;
- raw-price preservation and adjustment flags;
- historical source completeness;
- strict event-dataset readiness;
- inherited event blockers;
- the SHA-256 of the integration JSON.

The composed readiness report additionally exposes:

- the audited bootstrap raw-price fingerprint;
- whether the evidence fingerprint matches the audited fingerprint;
- universe and window matches;
- granular blockers;
- the active price-treatment mode.

A raw-price mismatch emits:

```text
CORPORATE_ACTION_PRICE_PROVENANCE_MISMATCH
```

and keeps the global price blocker.

## Price-treatment modes

- `ADJUSTED_CLOSE`
- `EVENT_AWARE_M15_STRICT`
- `EVENT_AWARE_M15_DIAGNOSTIC_ONLY`
- `RAW_UNADJUSTED_UNRESOLVED`

The current public-data smoke remains diagnostic. It builds event evidence for
MGLU3/ITSA4/B3SA3/AMER3 while the global readiness sample is PETR4/VALE3/ITUB4. Both universe and
raw-price provenance therefore differ by design, proving that capability evidence cannot expand
outside its audited artifacts.

## Readiness effect

This bridge does not remove any current historical blocker. It creates the legitimate future path
for raw COTAHIST to become strict-ready once event completeness, exact scope and exact price
provenance are all established. M16 weight promotion remains a separate out-of-sample gate.
