# Post-M20 — B3 event-aware historical coverage audit

Status: **diagnostic coverage contract implemented; historical source completeness remains fail-closed**.

## Why this block exists

The validated corporate-action conversion contracts prove that selected B3 cash distributions,
share-ratio events and subscription rights can be represented in M15 without rewriting raw
COTAHIST. That does not by itself prove that a historical return path has every corporate action
required to reconstruct economic return.

The readiness layer therefore keeps two questions separate:

1. can every relevant event observed for a ticker be converted into a supported M15 event?
2. does the source prove that the observed events are the complete historical event set?

## Cash distributions

The B3 dividend collector preserves `lastDatePrior` and the event conversion does not silently treat
that value as the economic EX session. The diagnostic conversion:

- reconciles ticker/ISIN security identity;
- requires the raw COTAHIST session on `lastDatePrior`;
- resolves the first actual trading session after that date;
- verifies event/security identity against surrounding COTAHIST evidence when available;
- requires a positive amount and a supported distribution kind;
- preserves source availability semantics;
- creates `CashDistribution` on the resolved EX trading session;
- never modifies `PriceBar.close` or manufactures `adjusted_close`.

Unsupported or ambiguous cash events remain blockers.

## Share actions

Supported bonus, split and reverse-split events use the validated ShareAction conversion contract.
Relevant events are scoped to the exact target security and must pass event-level COTAHIST factor,
session and identity checks. Unsupported labels remain explicit blockers.

## Subscription rights

Post-M20 preparation supports a subscription right as an **economic-value distribution** when the
required B3/COTAHIST evidence is available. The conversion uses the validated B3 reference-value
method and requires, fail-closed:

- subscription percentage;
- subscription price;
- security identity;
- last cum-rights session/price;
- first actual ex-rights trading session;
- source/event timing needed by the conversion contract.

The resulting value is represented as a separate `CashDistribution` input for realized-return
accounting. It does not pretend the right is a stock bonus, does not force exercise and does not
assume an additional capital contribution by the investor. A non-economic right can validly produce
zero distributed economic value and does not by itself validate an event-aware comparison.

## Event ordering

M15 processes explicit corporate-action inputs chronologically and keeps share-ratio and economic
value events separate. Ambiguous same-session ordering must be handled by data preparation rather
than silently inferred when contractual ordering could change economic value.

## Two readiness levels

`observed_event_coverage_complete` answers whether every relevant event visible in the bounded
current B3 company-supplement payload was safely handled.

`historical_source_completeness_proven` answers the stronger question required for strict historical
replay. It remains `false`: the free public company-supplement contract has not been established as
an exhaustive immutable historical event archive for arbitrary past cutoffs.

Therefore strict audits retain `B3_SUPPLEMENT_HISTORICAL_COMPLETENESS_UNPROVEN` and related dataset
source-completeness blockers, while:

- `strict_event_aware_backtest_ready = false`;
- `readiness_promotion_allowed = false`;
- raw B3 COTAHIST remains unchanged.

## Live evidence

The dedicated event-aware smoke uses bounded real B3/COTAHIST samples to exercise multiple corporate
action classes and verify raw-price preservation, event conversion, subscription-right handling and
fail-closed source-completeness behavior.

The historical readiness smoke separately aligns corporate-action evidence to the exact bounded
readiness universe, date window and raw-price fingerprint before accepting it as diagnostic M15
capability evidence. Even a fully matched diagnostic artifact cannot promote strict readiness while
historical source completeness remains unproven.

## Closure decision

Observed corporate-action mechanics are implemented and testable. The remaining
`B3_SUPPLEMENT_HISTORICAL_COMPLETENESS_UNPROVEN` condition is an external source-contract limitation,
not unfinished corporate-action architecture. It should be revisited only if a stronger historical
source/completeness contract becomes available.
