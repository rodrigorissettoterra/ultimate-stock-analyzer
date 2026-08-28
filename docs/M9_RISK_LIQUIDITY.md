# M9 — Risk and Liquidity

Status: **implemented in v0.9**.

## Objective

M9 keeps two questions separate:

1. **RiskSafetyScore** — how defensive has the security's observed return path been?
2. **LiquidityScore** — how easily can the security be traded using observable B3 market data?

Both scores expose their underlying metrics. Neither is a forecast, and neither changes the
company's Structural Score.

## Downside-risk metrics

The deterministic risk engine calculates:

- maximum drawdown;
- annualized volatility;
- annualized downside deviation;
- 95% historical one-session VaR;
- 95% historical one-session CVaR / expected shortfall;
- worst rolling 20-session return.

A helper for downside beta is also available when aligned benchmark returns are supplied.

`RiskSafetyScore` uses transparent piecewise hypothesis anchors, with higher values meaning a
more defensive historical risk profile. Raw unadjusted B3 prices lower confidence because
corporate actions can create artificial return jumps. The engine does not silently repair them.

## Liquidity metrics

The liquidity engine uses:

- 20- and 60-session average daily traded financial volume (ADTV);
- median number of trades over 20 sessions;
- latest B3 best-bid / best-ask percentage spread when available;
- fraction of zero-volume sessions;
- average 20-session traded quantity / free-float shares when free float is available.

The public COTAHIST parser now preserves the best bid and best ask fields in addition to OHLC,
trade count, quantity and financial volume.

Free-float turnover is optional. If it is missing, the engine reduces data coverage instead of
inventing a value.

`days_to_liquidate()` is an explicit capacity helper requiring position value, ADTV and maximum
participation rate. No portfolio size is assumed by the agent.

## Score semantics

- `RiskSafetyScore`: 100 = more defensive under v0.9 historical-risk anchors.
- `LiquidityScore`: 100 = easier to trade under v0.9 observable-liquidity anchors.

Weights and thresholds are hypotheses pending M15/M16 point-in-time and walk-forward validation.
VaR, CVaR and the composite scores must never be presented as loss guarantees or future-risk
bounds.
