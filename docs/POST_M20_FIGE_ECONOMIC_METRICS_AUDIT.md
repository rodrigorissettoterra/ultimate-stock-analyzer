# Post-M20 — FIGE Economic Metrics Audit

## Status

This block is diagnostic only.

It consumes the already validated `fige_financial_cvm_v1` accounting contract for
`cvm:6041` and tests whether candidate financial-company metrics are economically
meaningful before any routing or scoring change.

It does **not**:

- add FIGE to a scoring model;
- change sector/model routing;
- change score weights or thresholds;
- change rankings;
- change historical backtests;
- treat latest-state CVM annual archives as strict revision-history PIT evidence.

## Why this audit exists

FIGE does not use the `general_corporate` CVM account semantics and has no exact
prudential IFData identity. The project therefore needs a non-prudential financial
interpretation built from FIGE's own validated CVM statements.

The accounting contract already establishes exact statement/account-code/label
bindings and fail-closed extraction. This block asks the separate question:

> Which ratios remain economically interpretable and sufficiently stable to become
> candidates for a future `financial_non_prudential` model?

Accounting availability is not the same as economic suitability.

## Evidence boundary

The audit uses annual individual DFP evidence for 2021-2025 and only values that first
pass `fige_financial_cvm_v1`.

Missing values remain `UNKNOWN` (`null` in the JSON artifact). A reported zero remains
a known zero.

The issuer-bounded CVM loader still filters exact `CD_CVM=6041` before normalization.
No ticker, name, group association or fuzzy identity matching is introduced.

## Candidate metrics

### Profitability

The audit calculates both closing-balance and, where a prior audited year exists,
average-balance variants:

- net income / closing equity;
- net income / average equity;
- net income / closing assets;
- net income / average assets;
- net income / closing financial assets;
- net income / average financial assets.

It also publishes the absolute difference between closing and average denominator
variants. This makes denominator sensitivity visible rather than hiding it inside a
single ROE/ROA number.

For the first audited year (2021), average-denominator variants remain `UNKNOWN` because
the audit deliberately does not silently reach outside the validated 2021-2025 window.

### Balance-sheet structure

The audit calculates:

- financial assets / total assets;
- securities at amortized cost / total assets;
- securities at amortized cost / financial assets;
- equity / total assets;
- financial liabilities at amortized cost / total assets;
- fiscal liabilities / total assets.

These ratios describe how FIGE is funded and where its assets are concentrated without
forcing an industrial leverage model onto the company.

### Intermediation and operating result

The audit calculates:

- gross financial intermediation result / closing assets;
- gross financial intermediation result / average assets;
- absolute intermediation expense / intermediation revenue;
- other operating result / gross intermediation result;
- pretax income / gross intermediation result.

The ratios use FIGE-specific financial-statement semantics. They are not EBIT, EBITDA,
gross margin or industrial operating-margin proxies.

### Taxes and result quality

The audit calculates:

- effective tax burden = `abs(IR/CS) / pretax income` when pretax income is positive;
- net income / pretax income;
- absolute difference between net income and continuing-operations income, divided by
  absolute net income.

The last ratio is a reconciliation diagnostic. A low value means little of reported
net income sits outside the continuing-operations line under the current statement
structure.

## Multi-year diagnostics

Across the audited years the artifact reports descriptive evidence including:

- positive-net-income year ratio;
- mean net income;
- population standard deviation of net income;
- coefficient of variation of net income;
- population standard deviation of closing and average ROE;
- population standard deviation of closing and average ROA;
- observed min/max financial-assets-to-assets;
- observed min/max equity-to-assets;
- maximum financial-liabilities-to-assets;
- maximum non-continuing-result reconciliation gap.

Five annual observations are useful diagnostic evidence, but they are not enough on
their own to establish a normative score threshold.

## Known 2022 distribution trap

FIGE had a known extraordinary distribution in 2022 of approximately R$ 99.6 million
against reserves.

Therefore this audit deliberately does **not** interpret raw growth or contraction of
equity/assets as economic quality. The 2022 annual audit carries an explicit warning,
and the historical report blocks `balance_growth_quality` under the current contract.

A future growth-quality metric would require normalized evidence for at least:

- DMPL;
- ordinary versus extraordinary distributions;
- reserve releases;
- capital contributions/reductions;
- other material equity adjustments.

## Dividend sustainability

`dividend_sustainability` remains `BLOCKED_WITH_CURRENT_CONTRACT`.

The existing FIGE accounting contract does not provide the distribution/DMPL evidence
needed to distinguish sustainable recurring payouts from extraordinary reserve
releases. The audit therefore does not synthesize payout ratios from incomplete
evidence.

## Metric dispositions

The report deliberately uses diagnostic dispositions rather than score eligibility:

| Metric group | Audit disposition | Meaning |
| --- | --- | --- |
| Profitability | `AUDITABLE_CANDIDATE` | Economically aligned, but denominator sensitivity must be reviewed. |
| Balance-sheet structure | `AUDITABLE_CANDIDATE` | Directly supported by FIGE-specific stable balance accounts. |
| Result composition | `AUDITABLE_CANDIDATE` | Directly supported by FIGE-specific DRE semantics. |
| Profit stability | `DESCRIPTIVE_ONLY` | Useful evidence, not a standalone threshold from five observations. |
| Balance growth quality | `BLOCKED_WITH_CURRENT_CONTRACT` | Extraordinary distributions/DMPL are not normalized. |
| Dividend sustainability | `BLOCKED_WITH_CURRENT_CONTRACT` | Distribution contract is still missing. |

`AUDITABLE_CANDIDATE` does **not** mean score-ready. Metric selection and score design
remain a later block after the live artifact is inspected.

## Synthetic tests

`tests/test_fige_economic_metrics_audit.py` covers:

- exact financial-profile calculations;
- average versus closing denominators;
- reported zero preserved as known zero;
- missing input preserved as `UNKNOWN`;
- invalid zero balance denominators fail closed to `UNKNOWN`;
- first-year average denominators remain `UNKNOWN`;
- explicit 2022 extraordinary-distribution warning;
- exact company identity enforcement;
- descriptive historical statistics;
- blocked metric groups;
- rejection of non-contiguous or duplicate fiscal-year series.

## Live smoke

Run:

```bash
python scripts/fige_economic_metrics_audit.py \
  --start-year 2021 \
  --end-year 2025 \
  --output fige-economic-metrics-audit.json
```

The script:

1. downloads each official annual CVM DFP archive;
2. filters exact FIGE issuer evidence before normalization;
3. audits the normalized statement tree;
4. evaluates `fige_financial_cvm_v1`;
5. requires 100% critical and total contract coverage;
6. calculates annual diagnostic ratios;
7. summarizes 2021-2025 stability/volatility;
8. writes the full evidence artifact;
9. fails if an essential diagnostic metric is unavailable.

The GitHub Actions workflow
`.github/workflows/fige-economic-metrics-audit-smoke.yml` publishes the JSON artifact
for inspection.

## Decision gate after this block

Before creating `financial_non_prudential`, inspect the real 2021-2025 artifact and
decide which candidate groups have:

- stable semantics;
- sensible values;
- acceptable denominator sensitivity;
- useful cross-year behavior;
- no hidden dependence on the extraordinary 2022 distribution;
- a clear treatment of missing data;
- economic comparability suitable for FIGE.

Only after that evidence may a later block define model configuration, deterministic
score formulas, routing, registry updates and the mandatory scoring/backtest regression
comparison.
