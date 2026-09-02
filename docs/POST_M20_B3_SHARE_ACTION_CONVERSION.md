# Post-M20 — B3 ShareAction conversion contract

Status: **conversion contract implemented; readiness unchanged**.

## Evidence basis

The prior B3 × COTAHIST audits established two independent issuers for each supported share-ratio
label while keeping raw B3 prices untouched:

- `BONIFICACAO` → `1 + factor / 100`;
- `DESDOBRAMENTO` → `1 + factor / 100`;
- `GRUPAMENTO` → `factor`.

The evidence was derived from raw COTAHIST discontinuities around the official B3 `lastDatePrior`
date. Events with conflicting share-class ISINs were rejected.

## Separation of responsibilities

The source-contract collector remains conservative. Missing `completeFactor` continues to be
reported as missing in the raw B3 contract audit; this block does not rewrite source truth.

The backtesting conversion layer separately applies the empirically validated label formulas only
when the individual event also passes identity and price-window checks.

## Conversion gate

A B3 stock event becomes `ShareAction` only when:

1. the normalized label is one of the three validated labels;
2. `factor` is positive and `lastDatePrior` exists;
3. if B3 supplies `completeFactor`, it does not conflict with the validated formula;
4. raw COTAHIST contains the exact COM session and the next EX trading session;
5. the event ISIN does not conflict with either COTAHIST session;
6. the event-level factor validator is empirically consistent;
7. the event's best candidate is exactly the formula authorized for that label.

The `ShareAction.ex_date` is the first actual trading session after `lastDatePrior`; the code never
assumes calendar `+1 day`.

## Unsupported events

Subscription rights and unknown/special stock-event labels remain fail-closed. They are not
approximated as simple share ratios.

## Economic regression

The live smoke reuses M15 `total_holding_return` and compares, for every converted event:

- raw price-only return across the COM→EX discontinuity;
- the same return with the generated `ShareAction`.

The event-aware absolute return must be smaller for every converted event and must remain within a
bounded plausibility threshold. This validates the economic effect without modifying historical
price bars.

## Non-effects

This block does **not**:

- set `PriceBar.adjusted_close`;
- overwrite raw COTAHIST;
- remove `PRICE_SERIES_UNADJUSTED_FOR_CORPORATE_ACTIONS`;
- promote strict historical backtest readiness or walk-forward readiness;
- run a production portfolio backtest;
- change scores, scoring weights, ranking, sector routing, valuation, recommendations or portfolio
  construction.

## Next step

After the live conversion regression is green and its artifact is inspected, a separate integration
block can decide how validated `ShareAction` events enter the historical backtest dataset. That
integration must rerun readiness and backtest comparisons before the raw-price blocker can be
removed or narrowed.
