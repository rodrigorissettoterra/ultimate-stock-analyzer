# Post-M20 — insurer dividend features

## Purpose

Reuse the project's B3 cash-distribution evidence for insurer-specific structural scoring without importing corporate cash-flow assumptions that do not fit financial institutions.

## Score-facing metrics

This adapter promotes only:

- `dividend_regularity`: the existing five-year dividend regularity score, evaluated only from events visible at `as_of`;
- `dividend_cagr_5y`: a strict CAGR over six consecutive completed calendar-year regular distributions, yielding an exact five-year endpoint interval.

`dividend_sustainability` remains `UNKNOWN`. The generic sustainability implementation materially uses free-cash-flow payout/coverage, and free cash flow is not a safe insurer analogue. It must not be reused just to increase coverage.

## Point-in-time contract

`point_in_time_payments(..., require_known_availability=True)` is mandatory. Payments without `available_from`, or whose availability is later than `as_of`, are excluded. The B3 collector derives a conservative availability timestamp from the approval date when that evidence exists.

The caller must pass events already scoped to one security/issuer economic exposure. This adapter performs no ticker/name/fuzzy identity matching.

## Strict dividend CAGR

If `as_of` is exactly December 31, that calendar year is considered completed; otherwise the last completed year is `as_of.year - 1`. The implementation then requires positive regular DIVIDEND/JCP distributions in every year from `end_year - 5` through `end_year`.

Extraordinary distributions do not count. Missing years, non-positive totals or non-finite values make the CAGR `UNKNOWN`; no interpolation or endpoint substitution is allowed.

## Coverage impact

In `insurance_v0.6`, `dividend_regularity` contributes 45% of the 10% Dividends category (4.5 percentage points) and `dividend_cagr_5y` contributes 15% (1.5 percentage points). Together they can add at most 6pp. `dividend_sustainability` remains unavailable, and the global 65% ranking gate is unchanged.
