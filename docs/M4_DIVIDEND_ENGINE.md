# M4 — Dividend/JCP Engine

## Objective

M4 separates three questions that are often incorrectly collapsed into dividend yield:

1. **Does the company distribute cash regularly?**
2. **How much of the observed yield depends on extraordinary distributions?**
3. **Are regular distributions covered by earnings and free cash flow?**

Dividend yield is reported, but a high yield alone is not rewarded as dividend quality.

## Source priority

1. B3 public listed-company corporate-actions data.
2. Issuer/CVM evidence where useful for validation.
3. Fundamentus only as a free fallback/cross-check.

The B3 public company page exposes cash-event fields such as `assetIssued`, `paymentDate`, `rate`,
`relatedTo`, `approvedOn`, `isinCode`, `label`, `lastDatePrior` and `remarks`. The collector keeps
these semantics instead of silently rewriting them.

## Date semantics

B3's `lastDatePrior` is the last date before the asset becomes EX. It is not necessarily safe to
convert it to the EX date by adding one calendar day because weekends and exchange holidays exist.
Until the market-calendar layer is implemented, the canonical payment stores that exact date with
`date_basis=LAST_DATE_PRIOR_TO_EX`.

For point-in-time research, when only the approval date is available, M4 uses a conservative
availability assumption: **the following calendar day at 00:00 UTC**. A later event-feed collector
with an exact publication timestamp can replace this approximation without changing downstream
contracts.

## Regularity

The default screen remains intentionally interpretable:

- positive dividend/JCP in at least four of the latest five calendar years;
- no regular-payment gap above approximately 18 months;
- extraordinary distributions do not establish regularity;
- current partial-year data can establish a payment year, but annual growth/stability calculations
  use completed calendar years only.

The profile also records longest annual streak, maximum payment gap, annual regular amounts,
12-month regular and extraordinary amounts, median annual amount, CAGR, coefficient of variation
and number of material annual cuts.

## Sustainability score

The initial, versionable hypothesis combines:

- 35% regularity;
- 25% FCF payout quality;
- 15% earnings payout quality;
- 15% distribution stability;
- 10% independence from extraordinary distributions.

Available components are reweighted when inputs are genuinely unavailable, and `data_coverage`
records how much of the model was evidenced. Negative earnings/FCF are not treated as missing:
they receive a zero component and an explicit flag.

These weights are not claimed to be optimal. They must be validated and calibrated in M15/M16
using point-in-time backtesting and sector-specific overrides.
