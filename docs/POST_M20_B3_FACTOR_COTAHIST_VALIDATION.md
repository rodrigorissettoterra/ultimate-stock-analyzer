# Post-M20 — B3 factor × COTAHIST validation

Status: **diagnostic only**.

## Context

The B3 corporate-actions contract audit proved that the live listed-company supplement exposes
`factor` for stock events but does not expose `completeFactor` in the observed official payload.
The same sample also proved that raw `factor` cannot be interpreted uniformly:

- bonus events can carry values such as `2` or `5`;
- reverse splits can carry values such as `0.1`;
- splits can carry values such as `300`.

No one formula is therefore promoted from the payload alone.

## Validation method

This block compares each supported event with raw B3 COTAHIST around `lastDatePrior`:

1. require an exact COTAHIST bar on the last COM trading date;
2. select the first trading bar after that date as the observed EX session;
3. verify event ISIN against the COTAHIST ISIN when both are available;
4. compute `previous close / next open` as the primary observed share-ratio signal;
5. retain `previous close / next close` as secondary context;
6. compare four candidate transformations of the B3 numeric `factor`:
   - `DIRECT_FACTOR = factor`;
   - `FACTOR_PERCENT = factor / 100`;
   - `ONE_PLUS_FACTOR_PERCENT = 1 + factor / 100`;
   - `INVERSE_FACTOR = 1 / factor`.

The close-to-next-open ratio is preferred because the mechanical corporate-action repricing occurs
between trading sessions. It still contains normal overnight market movement, so an empirical
match is evidence rather than an exact accounting identity.

## Event-level gate

A candidate is marked `EMPIRICALLY_CONSISTENT` only when:

- the best candidate has at most 15% relative error versus close-to-next-open;
- the second-best candidate is at least 10 percentage points worse;
- the exact COM and next trading bars exist;
- identity evidence does not conflict.

Ties or weak separation remain `AMBIGUOUS_FACTOR_TRANSFORM`.

## Label-level promotion evidence

The diagnostic label summary requires at least:

- 2 empirically consistent events; and
- 2 different issuing companies;

before `promotion_ready` can become true for one label. Even then, this flag is only evidence for a
future implementation block. This block never installs the formula into backtesting.

## Bounded live sample

The smoke uses:

- `MGLU:MGLU3`, because its current B3 history includes bonus, reverse-split and split events;
- `ITSA:ITSA4`, adding a second issuer and an identity cross-check for bonus events.

COTAHIST years are resolved from the B3 event dates and downloaded only for the required tickers.
The artifact retains every evaluated event, all candidate ratios/errors and label summaries.

## Non-effects

This block does **not**:

- create `ShareAction` objects;
- set `PriceBar.adjusted_close`;
- alter raw COTAHIST prices;
- remove `PRICE_SERIES_UNADJUSTED_FOR_CORPORATE_ACTIONS`;
- change strict historical backtest or walk-forward readiness;
- change scores, sector routing, weights, rankability, valuation, recommendations or portfolio
  behavior.

## Next step

Inspect the live artifact. A label-specific transformation can move to an implementation contract
only after the observed events are coherent enough for the label-level evidence rule. Unsupported
stock events and subscription rights remain fail-closed regardless of factor behavior.
