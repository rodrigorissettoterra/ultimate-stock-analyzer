# Post-M20 Gate — Historical Backtest Readiness Audit

Status: **implemented diagnostic gate**.

This gate answers a narrower question than M15 itself: **does one materialized public-data
bootstrap run contain evidence that is safe to feed into strict point-in-time historical
scoring/backtesting?**

It does not run an investment strategy, optimize weights or promote M16 candidates. A negative
readiness result is a valid outcome.

## Why this gate exists

M15 and M16 are implemented engines, but their anti-bias contracts require more than
historical-looking rows. Evidence must have historical identity, publication timing and source
semantics that were actually knowable at the simulated date.

The current free/public bootstrap already preserves useful historical evidence, but several source
contracts are deliberately conservative:

- CVM DFP lines carry publication timing and can contribute to point-in-time fundamental coverage;
- annual CVM FCA archives provide historical security/ticker identity;
- B3 COTAHIST provides official historical quotes, but they are preserved unadjusted;
- the B3 sector workbook is a **current snapshot**, not a revision-aware historical classification
  series;
- BCB IFData historical rows are latest-state API observations without revision history, so
  normalized bank profiles remain non-PIT for strict backtests.

The audit makes those boundaries machine-readable instead of allowing a later backtest to infer
readiness from file dates alone.

## Reported checks

For one verified `BootstrapDataset`, the report includes:

- fundamental company-year count;
- company-years with 100% point-in-time critical accounting coverage;
- count and exact attribution of company-years with incomplete fundamental PIT coverage;
- for each fundamental PIT gap: exact company ID, fiscal year, tickers, accounting contract,
  applicability, sector model, missing critical inputs, untimed critical inputs and cause codes;
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

The report is sanitized. Raw CVM/B3/BCB payloads remain only inside the temporary/local bootstrap
data directory and are not uploaded by the readiness workflow.

### Fundamental PIT gap attribution

`FUNDAMENTAL_POINT_IN_TIME_COVERAGE_INCOMPLETE` is intentionally a summary blocker. It does not
necessarily identify an independent source defect.

Schema `1.1` adds `fundamental_point_in_time_gaps` so the audit can distinguish:

```text
CRITICAL_INPUTS_MISSING
CRITICAL_INPUTS_NOT_POINT_IN_TIME
SPECIALIZED_EVIDENCE_NOT_POINT_IN_TIME
UNATTRIBUTED_POINT_IN_TIME_GAP
```

For bank company-years using the verified IFData contract, latest-state IFData evidence is
represented by both the existing `BANK_EVIDENCE_NOT_POINT_IN_TIME` source blocker and a company-year
gap attributed as `SPECIALIZED_EVIDENCE_NOT_POINT_IN_TIME`. This is deliberate diagnostic overlap:
the first identifies the source-level limitation, while the second identifies exactly which
fundamental company-years inherit it.

The live audit passes the complete list of `FundamentalCoverageRecord` objects into the readiness
gate and requires the number of detailed gaps to match the summary count. A mismatch fails rather
than silently publishing a partial attribution.

### Corporate-action readiness attribution

Schema `1.2` is produced by a composition layer after the base readiness audit. It does not change
how fundamental, sector, bank, security or price coverage is measured.

The corporate-action bridge records separately:

- whether the bounded M15 event-aware path was actually exercised;
- the ticker and date scope of that evidence;
- whether the scope covers the readiness request;
- whether raw COTAHIST was preserved;
- whether historical event-source completeness is proven;
- whether the event dataset is strict-backtest ready;
- the SHA-256 fingerprint of the integration report;
- granular corporate-action blockers and the active price-treatment mode.

This means raw COTAHIST does not need a synthetic `adjusted_close` to become strict-ready in the
future. `PRICE_SERIES_UNADJUSTED_FOR_CORPORATE_ACTIONS` can be removed only when a validated M15
`ShareAction`/`CashDistribution` path is backed by complete event evidence for the exact requested
universe and historical window. A capability smoke for one sample can never unlock another sample.

See `POST_M20_HISTORICAL_READINESS_CORPORATE_ACTION_BRIDGE.md` for the full contract.

## Current expected blockers

For the current source contract, a bounded live smoke is expected to expose at least:

```text
SECTOR_ROUTING_NOT_POINT_IN_TIME
BANK_EVIDENCE_NOT_POINT_IN_TIME
PRICE_SERIES_UNADJUSTED_FOR_CORPORATE_ACTIONS
```

`FUNDAMENTAL_POINT_IN_TIME_COVERAGE_INCOMPLETE` can also appear when a specialized company-year
depends on latest-state evidence such as IFData. The granular attribution makes clear when this is
the same underlying source limitation rather than a separate CVM publication-timing failure.

When bounded corporate-action integration evidence is attached, additional blockers can explain why
the event-aware path remains diagnostic, including source-completeness, strict-dataset, ticker-scope
and date-window limitations.

These blockers must **not** be removed by weakening M15 rules. They are resolved only by obtaining
revision-aware historical evidence or by supplying a correctly adjusted/event-aware price history
with a defensible completeness contract.

## Live smoke

The GitHub Action runs a deliberately bounded two-completed-year window for:

- `PETR4` — general corporate path;
- `VALE3` — general corporate path;
- `ITUB4` — bank/IFData path.

It requires complete FCA security and COTAHIST ticker/year presence for the bounded sample, then
succeeds only if the known non-PIT/unadjusted source blockers are detected. It also requires
complete company-year attribution for every fundamental PIT gap. In other words, **green means
the audit
failed closed correctly and explained the failure coherently**, not that production backtesting is
now approved.

The same workflow also materializes the established MGLU3/ITSA4/B3SA3/AMER3 event-aware M15
capability sample and attaches its fingerprinted JSON to the readiness report. The intentional
universe mismatch proves that valid engine evidence remains scope-bounded and cannot promote the
PETR4/VALE3/ITUB4 readiness result.

## Relationship to M15/M16

`strict_historical_backtest_data_ready=true` means the evidence contract checked by this gate has no
known blocker. It does not claim that a strategy has positive performance.

`walk_forward_data_ready=true` means the same checked evidence can proceed to M16 data preparation.
The audit explicitly leaves `weight_promotion_evaluated=false`; promotion still requires the OOS
gates documented in M16 and cannot be inferred from data readiness alone.

## Next empirical work

The current blockers point to the next data tasks rather than to model changes:

1. revision-aware historical sector/applicability evidence, or an equally auditable historical
   routing source;
2. complete, scope-bounded corporate-action evidence for raw COTAHIST event-aware returns;
3. revision-aware specialized bank evidence if bank observations are to participate in strict PIT
   calibration;
4. a sufficiently broad multi-regime local dataset, kept outside Git, followed by M15 backtests and
   only then M16 walk-forward evaluation.
