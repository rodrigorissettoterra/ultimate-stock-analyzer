# M15 — Point-in-Time Backtesting

Status: **implemented in v1.5 candidate**.

M15 evaluates historical portfolio decisions without allowing today's knowledge to leak into the
past.

## Hard anti-bias rules

- a score is visible only after its `available_at` timestamp;
- a restatement/recalculation cannot replace the historical version before its publication;
- universe membership is historical, so currently delisted companies remain in old simulations;
- signals decided at day-end execute only on the next available trading session;
- a missing selected-asset price path fails closed by default instead of becoming artificial cash;
- benchmark price paths are mandatory;
- transaction costs and configurable slippage are charged from turnover.

## Corporate actions

v1.5 models cash distributions and share-ratio events (splits, reverse splits and stock bonuses)
explicitly and chronologically. Subscription rights are not silently approximated. A dataset
requiring those events must provide a correctly adjusted series or be rejected/flagged by data
preparation.

Post-M20 historical preparation now has a dedicated event-aware dataset adapter. It preserves raw
B3 COTAHIST, materializes empirically validated `ShareAction` and supported `CashDistribution`
objects as separate M15 inputs, fingerprints the source bars, and is strict by default. Because the
latest-state B3 supplement still does not prove historical event completeness, diagnostic execution
requires an explicit non-strict opt-in and cannot promote readiness or M16 weights. See
`POST_M20_HISTORICAL_EVENT_DATASET_M15_INTEGRATION.md`.

## Portfolio model

The first reference policy is an equal-weight top-N portfolio ranked by Investment Attractiveness.
This is intentionally simple: M15 tests whether the score contains historical information before
M16 attempts any weight calibration.

## Metrics

The performance layer reports total return, CAGR, benchmark CAGR, annualized alpha, beta,
volatility, Sharpe, Sortino, maximum drawdown, Calmar, Information Ratio, positive-period hit rate,
benchmark hit rate and turnover.

## Not empirical optimization

No M14 weight is changed in M15. M16 will perform walk-forward calibration using training windows
that strictly precede their evaluation windows.
