# Post-M20 — B3 Corporate Actions Contract Audit

Status: **diagnostic only**.

## Why this block exists

The historical-readiness gate correctly keeps B3 COTAHIST prices blocked because those prices are
not adjusted by the project for corporate actions. M15 already supports explicit `ShareAction`
and `CashDistribution` events in total-return calculation, so the correct next step is to validate
the official event contract rather than invent an adjusted-close series.

The project already uses the B3 listed-company supplement endpoint for cash dividends. The same
payload exposes `stockDividends` and `subscriptions`.

## Current B3 response shape

The listed-company supplement has been observed in two compatible transport shapes:

- the company supplement object directly; or
- a single-item list whose only element is that object.

The collector now normalizes only those two cases. Empty lists, lists with multiple objects,
non-object list items and other root types fail closed with `TypeError`. This is deliberate: the
project does not guess which company object to select if the upstream contract changes.

This compatibility correction also preserves the existing cash-dividend parser because both cash
and stock events share the same B3 supplement response.

## Fail-closed stock-event contract

Only these normalized stock-event labels are candidates for a future `ShareAction` conversion:

- `BONIFICACAO`;
- `DESDOBRAMENTO`;
- `GRUPAMENTO`.

The raw numeric `factor` is **not** promoted directly to `ratio_new_per_old`. Public consumers of
the B3 payload describe that field with mixed factor/percentage semantics. When the payload also
provides an explicit `completeFactor` such as `1,02 para 1`, the audit parses that ratio and checks
whether the numeric `factor` agrees with it.

A stock action becomes `READY_COMPLETE_FACTOR` only when:

1. its normalized label is allowlisted;
2. `lastDatePrior` is present;
3. `completeFactor` is present and parses into a positive `new / old` ratio;
4. when numeric `factor` is present, it does not conflict with that explicit ratio.

All other cases stay blocked with an explicit reason. No fallback guesses are allowed.

## Subscription rights

Every row under `subscriptions` is retained as evidence and marked
`UNSUPPORTED_SUBSCRIPTION_RIGHTS`. M15 explicitly does not approximate subscription rights, so this
block does not convert a subscription percentage or issue price into a share-ratio event.

## Live evidence

The GitHub smoke audits a bounded live sample (`ITSA`, `MGLU`) against the B3 public listed-company
supplement endpoint. The artifact records:

- top-level payload keys;
- observed stock-action labels;
- raw `factor` and optional `completeFactor`;
- dates, ISIN and remarks;
- conversion status for each stock event;
- subscription rows and blockers;
- aggregate counts and whether the contract is safe for a future conversion block.

The smoke intentionally succeeds when ambiguous or unsupported cases are reported correctly. Green
means the contract was audited fail-closed, not that historical prices are now backtest-ready.

## Non-effects

This block does **not**:

- create `ShareAction` objects from live B3 data;
- adjust COTAHIST price bars;
- change `PRICE_SERIES_UNADJUSTED_FOR_CORPORATE_ACTIONS`;
- change sector routing, scoring, weights, valuation, recommendations or rankability;
- promote M15/M16 historical readiness.

## Next decision

Inspect the live artifact. If explicit ratio evidence is consistently available and coherent for
supported labels, the next block may validate those ratios empirically against the COTAHIST price
discontinuity before adding a separately tested conversion into M15 `ShareAction` events. If the
live B3 contract omits or ambiguously encodes the ratio, the relevant historical paths remain
abstained rather than inferring a factor.
