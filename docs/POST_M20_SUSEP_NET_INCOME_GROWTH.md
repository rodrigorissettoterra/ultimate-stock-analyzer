# Post-M20 — SUSEP insurer net-income growth

## Purpose

Add the verified insurer `net_income_cagr_5y` growth feature without mixing accounting eras, reconstructing cumulative P&L incorrectly, or inventing a transformation for loss-making endpoints.

## Official field

The current SUSEP `Ses_campos.csv` dictionary independently confirms CMPID `518` as the net-income / loss line used by the insurer profitability contract. The same exact field is therefore reused here.

## Annual observation

Income-statement rows are cumulative within the fiscal year. The annual net-income observation is the December (`YYYY12`) CMPID `518` value. Monthly values are never summed.

## Five-year contract

For fiscal year `Y`, the implementation requires exactly one numeric December CMPID `518` observation for every year from `Y-5` through `Y`, inclusive. This creates six consecutive annual observations and an exact five-year endpoint interval.

The contract starts only when `Y-5 >= 2014`, matching the project's current SUSEP accounting-era boundary. No interpolation is allowed. Missing or duplicate evidence makes the history incomplete and the metric `UNKNOWN`.

When complete history exists, CAGR is calculated only if both endpoint net-income values are strictly positive:

`net_income_cagr_5y = (net_income_Y / net_income_Y-5) ** (1/5) - 1`

Intermediate years may contain losses: they remain valid observed history and are not interpolated away. A zero or negative starting or ending value makes CAGR economically ambiguous, so the metric remains `UNKNOWN` while `complete_history=true` records that the six-year evidence itself is complete.

## Identity and PIT boundaries

The function accepts only the exact numeric SUSEP company identifier. No ticker/name/fuzzy fallback exists. Current SUSEP historical data remain latest-state/revision-prone, so `point_in_time_eligible=false` is preserved.

## Coverage impact

`net_income_cagr_5y` carries 45% of the insurer Growth category. With Growth weighted at 10%, a valid value can add 4.5 percentage points of structural coverage. The ranking gate remains 65%; this implementation does not lower or bypass it.
