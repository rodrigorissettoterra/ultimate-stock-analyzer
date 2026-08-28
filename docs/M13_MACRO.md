# M13 — Macro Context and Sector Sensitivity

Status: **implemented in v1.3 candidate**.

## Principle

There is no universal "good macro" score. The same factor can affect sectors differently. M13
therefore separates:

1. **Factor State** — where a macro series sits relative to its own history and recent change;
2. **Sensitivity Profile** — a versioned sector hypothesis about whether high/rising values tend
   to help or hurt that business model;
3. **Macro Context Score** — deterministic combination with visible contributions, coverage and
   confidence.

The initial sensitivities are hypotheses, not causal estimates. M15/M16 will test and calibrate
them point-in-time.

## Free-first sources

- **Banco Central do Brasil / SGS** — official time-series interfaces in JSON/CSV. The project
  already has a generic SGS collector and M13 adds canonical normalization. The starter registry
  includes only explicitly verified series and can be expanded safely.
- **IBGE / SIDRA** — official table API. Because dimensions vary substantially by table, the
  collector accepts an explicit SIDRA query path and the normalizer requires explicit period/value
  fields. Missing or inhibited SIDRA symbols are skipped, never converted to zero.
- **IpeaData** remains an optional free fallback when a required series is not adequately covered
  by BCB/IBGE. M13 does not add a source merely for redundancy.

External commodity observations can use the same `MacroObservation` contract. No paid commodity
feed is required by the engine.

## Factor state

For each factor, M13 computes the latest level percentile within available history. When sufficient
history exists it also ranks a configurable lagged change. Both are mapped to -1..+1 and combined
with transparent weights. Data history controls confidence.

This is intentionally robust and explainable. It avoids fitting a predictive regression before the
point-in-time backtesting infrastructure exists.

## Sensitivity profiles

v1.3 includes initial profiles for:

- general corporates;
- banks;
- insurance;
- utilities;
- real estate;
- commodity exporters.

A coefficient near zero means the effect is deliberately treated as ambiguous/small. Company-level
overrides can be introduced later only with explicit evidence.

## Scenario analysis

`analyze_macro_scenario()` accepts normalized factor shocks in [-1, 1] and applies the same
sensitivity profile. This enables transparent stress tests without pretending to forecast the
future path of Selic, FX, inflation or commodity prices.
