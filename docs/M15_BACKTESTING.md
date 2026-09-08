# M15 — Point-in-Time Backtesting

Status: **implemented**.

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

M15 models cash distributions and share-ratio events (splits, reverse splits and stock bonuses)
explicitly and chronologically. Post-M20 preparation also supports subscription rights as an
**economic-value distribution**, using the validated B3 reference-value method when the required
percentage, subscription price, security identity, last cum-rights session and first ex-rights
trading session are all available. This does not assume that the investor exercised the right or
contributed additional capital.

The historical event-aware dataset adapter preserves raw B3 COTAHIST, materializes validated
`ShareAction` and supported `CashDistribution` objects as separate M15 inputs, and fingerprints the
source bars. Incomplete or ambiguous observed-event evidence is preserved as explicit blockers. It
prevents strict event-aware execution; diagnostic execution may still evaluate materialized events
with those blockers surfaced as warnings, without modifying raw prices or promoting readiness.

Observed-event handling and historical source completeness remain separate questions. The current
free public B3 supplement contract does not prove an exhaustive immutable historical corporate-action
ledger for arbitrary past `as_of` dates. Therefore diagnostic execution may validate mechanics, but
strict execution remains blocked until source completeness is proven. Diagnostic execution cannot
promote readiness or M16 weights. See `POST_M20_HISTORICAL_EVENT_DATASET_M15_INTEGRATION.md` and
`POST_M20_HISTORICAL_READINESS_CORPORATE_ACTION_BRIDGE.md`.

## Portfolio model

The first reference policy is an equal-weight top-N portfolio ranked by Investment Attractiveness.
This is intentionally simple: M15 tests whether the score contains historical information before
M16 attempts any weight calibration.

## Metrics

The performance layer reports total return, CAGR, benchmark CAGR, annualized alpha, beta,
volatility, Sharpe, Sortino, maximum drawdown, Calmar, Information Ratio, positive-period hit rate,
benchmark hit rate and turnover.

## Empirical boundary

No M14 weight is changed merely because M15 is implemented or because a diagnostic event-aware path
works. A strict full-history run is admissible only when the bounded readiness contract accepts the
underlying point-in-time evidence. When a public source cannot prove historical replay/completeness,
the correct result is abstention rather than an optimistic backfill.
