# Post-M20 — Historical corporate-action dataset and M15 integration

Status: **implemented as a fail-closed integration layer; no historical-readiness promotion**.

## Objective

Connect the already validated B3 corporate-action conversions to the M15 backtesting engine without
rewriting public B3 COTAHIST prices or pretending that the current B3 listed-company supplement is a
complete historical event archive.

The integration separates three questions that were previously easy to conflate:

1. can an observed B3 event be converted safely into a `ShareAction` or `CashDistribution`?
2. can those converted events be passed to M15 without changing raw COTAHIST?
3. is the historical event source complete enough to claim a strict point-in-time backtest?

The first two can be true while the third remains false.

## Contract

`historical_event_dataset.py` materializes an M15-compatible dataset from one or more
`B3EventAwareCoverageAudit` reports and the corresponding raw `PriceBar` rows.

The materialized dataset contains:

- raw close-derived `PricePoint` rows;
- empirically validated `ShareAction` rows;
- validated cash distributions;
- one SHA-256 fingerprint over the raw COTAHIST inputs;
- observed-event blockers;
- strict historical-source blockers;
- optional CVM/IPE corroboration status;
- explicit readiness flags.

Raw `PriceBar.close` values are never overwritten. The materializer rejects inputs whose
`adjusted_close` is already populated so that the same corporate action cannot be silently applied
twice.

## M15 bridge

`run_event_aware_m15_backtest()` passes the materialized `ShareAction` and `CashDistribution`
objects directly to the existing M15 `run_rebalance_backtest()` path.

The adapter is strict by default. If the dataset does not prove historical source completeness, the
call fails before running the backtest.

A caller may explicitly request diagnostic mode with `require_strict=False`. In that mode:

- M15 receives the validated observed events;
- the result carries `DIAGNOSTIC_EVENT_AWARE_BACKTEST` plus the strict blockers;
- no readiness or M16 weight promotion is allowed.

`compare_raw_and_event_aware_m15()` runs the same M15 inputs twice, first with raw COTAHIST only and
then with the validated event inputs. This is evidence about integration and mechanical price
continuity, not an investable performance claim.

## CVM/IPE role

The existing CVM/IPE corporate-action ledger can be attached to the materializer. Its filing ledger
is useful to corroborate observed B3 events and their issuer/reference-date trail.

It is deliberately not treated as proof that every historical corporate action has been enumerated.
CVM/IPE documents remain unstructured at the event-term level, security-class scope is not fully
proven, and revision-history completeness is still unresolved. Incomplete corroboration therefore
adds a blocker; complete corroboration of observed events does not remove the B3 historical-source
completeness blocker by itself.

## Readiness impact

This block does **not** remove `PRICE_SERIES_UNADJUSTED_FOR_CORPORATE_ACTIONS` from the global
historical readiness audit.

The narrower conclusion is now stronger and auditable:

- M15 has a tested event-aware input path;
- raw COTAHIST remains immutable;
- observed splits/reverse splits/bonuses and supported cash distributions can be materialized;
- the latest-state B3 supplement still does not prove that no historical event is missing;
- strict historical M15/M16 remains blocked until source completeness is independently established
  or the production historical contract is explicitly bounded to a window with defensible complete
  event evidence.

## Live smoke

The dedicated smoke uses the existing bounded sample:

- MGLU3;
- ITSA4;
- B3SA3;
- AMER3;
- 2024–2025 COTAHIST plus the next year only when needed to locate the first actual EX trading
  session after a year-end event.

The smoke requires:

- multiple validated `ShareAction` rows to be materialized;
- raw price fingerprinting;
- zero price overwrites;
- preservation of `B3_SUPPLEMENT_HISTORICAL_COMPLETENESS_UNPROVEN`;
- strict M15 readiness to remain false;
- a diagnostic raw-vs-event-aware M15 comparison to execute through the production M15 engine;
- no readiness or M16 promotion.

## Next step

Use this integration layer when assembling the broader historical dataset. The next readiness step is
not another return-formula change; it is to prove or explicitly bound corporate-action source
completeness, then rerun the global historical-readiness gate together with the remaining sector and
bank PIT blockers.
