# Post-M20 — B3 event-aware historical coverage audit

Status: **diagnostic coverage contract added; historical readiness remains blocked**.

## Why this block exists

The validated ShareAction conversion contract proved that selected B3 bonus, split and reverse-split
events can remove mechanical COTAHIST discontinuities without rewriting raw prices. That does not by
itself prove that a historical M15 return path has every corporate action required to reconstruct
economic return.

The readiness layer currently treats every raw COTAHIST bar without `adjusted_close` as a global
blocker. Before that rule can be narrowed, the system needs explicit evidence for two different
questions:

1. can every relevant event observed for a ticker be converted into an M15 event?
2. does the source prove that the observed events are the complete historical event set?

This audit keeps those questions separate.

## Cash distributions

The existing B3 dividend collector intentionally preserves `lastDatePrior` in
`DividendPayment.ex_date` and marks the basis as `LAST_DATE_PRIOR_TO_EX`. For M15 that value cannot
be passed directly as the economic EX date.

The new diagnostic conversion:

- accepts B3 `assetIssued` in either observed form: ticker or security ISIN;
- reconciles `assetIssued`, `isinCode` and the COTAHIST security identity instead of assuming the
  field is always a ticker;
- requires the raw COTAHIST session on `lastDatePrior`;
- resolves the first actual trading session after that date;
- verifies B3 event ISIN against the surrounding COTAHIST identity when available;
- requires a positive amount and an explicit `DIVIDEND` or `JCP` kind;
- preserves `available_from` and rejects an unknown or post-EX availability timestamp for the
  point-in-time conversion path;
- creates `CashDistribution` on that resolved EX trading session;
- never modifies `PriceBar.close` or sets `adjusted_close`.

Unsupported or unparsed relevant cash events remain blockers rather than being silently dropped.

## Share actions

The audit reuses the already validated ShareAction conversion contract. Relevant stock events are
scoped to the exact target security. Supported bonus, split and reverse-split events must pass the
existing event-level COTAHIST factor and identity checks.

Unsupported relevant stock labels remain explicit blockers.

## Subscriptions and ordering

Subscription rights remain unsupported in M15 and therefore block observed event coverage.

M15 currently processes a ShareAction before a CashDistribution when both share the same EX date.
Because that ordering can change the cash amount per original share, this audit marks any observed
same-session share/cash combination with
`SAME_SESSION_SHARE_AND_CASH_ORDERING_UNVERIFIED`. It does not assume the default ordering is
economically correct.

## Two readiness levels

`observed_event_coverage_complete` answers only whether every relevant event visible in the current
B3 company-supplement payload was safely handled.

`historical_source_completeness_proven` is intentionally `false`. The current supplement endpoint is
a latest-state company view; this project has not yet established an official historical archive or
revision-history contract proving that the endpoint contains every event needed for an arbitrary
past backtest window.

Therefore every strict audit retains
`B3_SUPPLEMENT_HISTORICAL_COMPLETENESS_UNPROVEN`, and:

- `strict_event_aware_backtest_ready = false`;
- `readiness_promotion_allowed = false`;
- `price_series_blocker_removed = false`;
- raw B3 COTAHIST remains unchanged.

## Live evidence

The smoke audits MGLU3, ITSA4, B3SA3 and AMER3 over 2024–2025. It requires:

- the full requested COTAHIST period for every sample ticker;
- multiple previously validated ShareAction conversions;
- multiple exact cash-distribution conversions;
- cash EX dates strictly after B3 `lastDatePrior`;
- the COTAHIST year after a relevant event year when needed to resolve a year-boundary EX session;
- the historical source-completeness blocker to remain present;
- no price adjustment or readiness promotion.

The smoke is allowed to report observed-event blockers. Its purpose is to expose them, not to hide
them in order to force a green readiness result.

## Next decision

If the live artifact confirms that observed share and cash events are mechanically usable, the next
evidence block should look for an official or otherwise defensible historical corporate-action
source with completeness semantics. Only after historical source completeness, unsupported event
classes and same-session ordering are resolved should
`PRICE_SERIES_UNADJUSTED_FOR_CORPORATE_ACTIONS` be narrowed or removed for event-aware paths.
