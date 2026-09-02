# Post-M20 Gate — Historical Backtest Readiness Audit

Status: **implemented diagnostic gate**.

This gate answers a narrower question than M15 itself: **does one materialized public-data bootstrap run contain evidence that is safe to feed into strict point-in-time historical scoring/backtesting?**

It does not run an investment strategy, optimize weights or promote M16 candidates. A negative readiness result is a valid outcome.

## Why this gate exists

M15 and M16 are implemented engines, but their anti-bias contracts require more than historical-looking rows. Evidence must have historical identity, publication timing and source semantics that were actually knowable at the simulated date.

The current free/public bootstrap already preserves useful historical evidence, but several source contracts are deliberately conservative:

- CVM DFP lines carry publication timing and can contribute to point-in-time fundamental coverage;
- annual CVM FCA archives provide historical security/ticker identity;
- B3 COTAHIST provides official historical quotes, but they are preserved unadjusted;
- the B3 sector workbook is a **current snapshot**, not a revision-aware historical classification series;
- BCB IFData historical rows are latest-state API observations without revision history, so normalized bank profiles remain non-PIT for strict backtests.

The audit makes those boundaries machine-readable instead of allowing a later backtest to infer readiness from file dates alone.

## Reported checks

For one verified `BootstrapDataset`, the report includes:

- fundamental company-year count;
- company-years with 100% point-in-time critical accounting coverage;
- longitudinal pair readiness;
- current sector-model resolution count;
- specialized accounting contracts still missing;
- number of sector-classification rows and how many are PIT eligible;
- number of IFData bank profiles and how many are PIT eligible;
- expected ticker/year pairs for bounded runs;
- FCA security ticker/year coverage;
- COTAHIST ticker/year coverage;
- adjusted versus unadjusted historical price bars;
- explicit blocker codes;
- `strict_historical_backtest_data_ready` and `walk_forward_data_ready` flags.

The report is sanitized. Raw CVM/B3/BCB payloads remain only inside the temporary/local bootstrap data directory and are not uploaded by the readiness workflow.

## Current expected blockers

For the current source contract, a bounded live smoke is expected to expose at least:

```text
SECTOR_ROUTING_NOT_POINT_IN_TIME
BANK_EVIDENCE_NOT_POINT_IN_TIME
PRICE_SERIES_UNADJUSTED_FOR_CORPORATE_ACTIONS
```

`FUNDAMENTAL_POINT_IN_TIME_COVERAGE_INCOMPLETE` can also appear when a specialized company-year depends on latest-state evidence such as IFData.

These blockers must **not** be removed by weakening M15 rules. They are resolved only by obtaining revision-aware historical evidence or by supplying a correctly adjusted/event-aware price history.

## Live smoke

The GitHub Action runs a deliberately bounded two-completed-year window for:

- `PETR4` — general corporate path;
- `VALE3` — general corporate path;
- `ITUB4` — bank/IFData path.

It requires complete FCA security and COTAHIST ticker/year presence for the bounded sample, then succeeds only if the known non-PIT/unadjusted source blockers are detected. In other words, **green means the audit failed closed correctly**, not that production backtesting is now approved.

## Relationship to M15/M16

`strict_historical_backtest_data_ready=true` means the evidence contract checked by this gate has no known blocker. It does not claim that a strategy has positive performance.

`walk_forward_data_ready=true` means the same checked evidence can proceed to M16 data preparation. The audit explicitly leaves `weight_promotion_evaluated=false`; promotion still requires the OOS gates documented in M16 and cannot be inferred from data readiness alone.

## Next empirical work

The current blockers point to the next data tasks rather than to model changes:

1. revision-aware historical sector/applicability evidence, or an equally auditable historical routing source;
2. corporate-action/dividend-aware or correctly adjusted historical price/return series;
3. revision-aware specialized bank evidence if bank observations are to participate in strict PIT calibration;
4. a sufficiently broad multi-regime local dataset, kept outside Git, followed by M15 backtests and only then M16 walk-forward evaluation.
