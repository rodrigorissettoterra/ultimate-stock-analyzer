# Post-M20 — FIGE Metric Selection Contract

## Status

This block converts the inspected 2021-2025 FIGE economic audit into an explicit,
versioned metric-selection contract for a possible future
`financial_non_prudential` model.

It is deliberately **not a scoring configuration**.

The contract cannot contain scoring weights, directions, targets, tolerances or
thresholds. Its parser rejects those fields. The output also remains:

- `score_ready = false`;
- `routing_ready = false`;
- `registry_resolvable = false`.

No sector registry, model routing, structural score, ranking, recommendation or
backtest behavior changes in this block.

## Why scoring remains blocked

The current structural engine normalizes `higher`/`lower` metrics by peer-adjusted
cross-sectional percentile. Its default sector-model requirement is eight comparable
peers.

For the FIGE-specific non-prudential accounting/economic contract, the current exact
validated peer set contains only:

- `cvm:6041` — FIGE.

With one observation, the structural normalizer returns a neutral percentile score and
zero peer reliability. Creating a routed FIGE score now would therefore create model
shape without economic comparison information.

The selection contract records:

- current exact comparable peer count: `1`;
- minimum cross-sectional peer count: `8`;
- scoring status: `BLOCKED_INSUFFICIENT_COMPARABLE_PEERS`.

This is a calibration/evidence constraint, not a software limitation to bypass.

## Primary uncalibrated candidates

### `roa_closing_assets`

Selected as the primary current profitability candidate.

Reasons:

- directly aligned with a financial asset-holding company;
- uses stable FIGE-specific accounts;
- available in all five audited years;
- avoids making equity distributions the primary profitability denominator;
- is less exposed than ROE to the known 2022 extraordinary distribution against
  reserves.

It is **not score-ready** until comparable peers exist.

### `pretax_income_to_gross_intermediation_result`

Selected as a primary result-retention candidate.

It measures how much FIGE-specific gross financial-intermediation result survives other
operating effects before tax. It avoids imposing EBIT/EBITDA semantics that do not
belong to FIGE's accounting plan.

### `other_operating_result_to_gross_intermediation_result`

Selected as a primary operating-burden candidate.

The metric preserves the actual sign of other operating result and makes non-
intermediation burden visible. Its eventual scoring direction and calibration are
intentionally absent from this contract.

## Secondary uncalibrated candidates

### `net_income_to_closing_financial_assets`

Economically valid, but secondary because FIGE's financial assets represent nearly all
of total assets. It is therefore strongly redundant with ROA on the observed evidence.
A future model should avoid double-counting the same profitability signal.

### `roe_closing_equity`

Economically valid, but secondary because the equity denominator is directly affected
by capital distributions.

The 2022 live artifact showed materially larger closing-versus-average ROE denominator
sensitivity than the following years, consistent with the already documented
extraordinary distribution. ROE should therefore not be the sole or primary FIGE
profitability signal without distribution normalization.

## Guardrails, not score drivers

The following metrics remain useful for applicability, drift and sanity checks:

- `financial_assets_to_assets`;
- `securities_to_financial_assets`;
- `equity_to_assets`;
- `financial_liabilities_to_assets`;
- `non_continuing_result_gap_to_abs_net_income`.

The live 2021-2025 evidence showed a highly saturated financial structure: almost all
assets were financial, equity funded nearly all assets, financial liabilities were
near zero, and the continuing-operations reconciliation gap was zero.

Those are strong profile/applicability signals. They are weak standalone quality-score
signals without a broader peer distribution.

## Diagnostic-only metrics

The contract retains but does not promote:

- average-balance ROE/ROA/financial-asset return;
- closing-versus-average denominator sensitivity;
- intermediation expense/revenue;
- fiscal liabilities/assets;
- gross intermediation result/assets;
- effective tax burden;
- net income/pretax income.

Important observed behavior:

- average-balance variants are intentionally `UNKNOWN` in 2021 because no unvalidated
  2020 balance is imported;
- the 2022 distribution remains visible through denominator-sensitivity diagnostics;
- intermediation expense/revenue was saturated at zero in the live five-year evidence;
- tax metrics were stable and auditable but are not sufficiently independent structural
  quality signals to justify weights at this stage.

## Descriptive-only history

Five-year statistics such as positive-income frequency, earnings coefficient of
variation and ROA volatility remain descriptive evidence only.

Five annual points for one issuer are not a defensible basis for normative thresholds.
Historical use also remains non-PIT for backtesting until publication/revision-aware
historical evidence is populated.

## Still blocked

### `balance_growth_quality`

Blocked until a dedicated contract normalizes at least:

- DMPL;
- capital contributions/reductions;
- ordinary distributions;
- extraordinary reserve releases;
- other material equity adjustments.

Raw 2022 equity contraction cannot be interpreted as deterioration because of the
known extraordinary distribution.

### `dividend_sustainability`

Blocked until FIGE-specific distribution/DMPL evidence distinguishes recurring payouts
from extraordinary reserve releases.

## Contract files

- `config/scoring/fige_financial_non_prudential_metric_contract_v0.1.yml`
- `src/ultimate_stock_analyzer/scoring/fige_metric_selection.py`
- `scripts/fige_metric_selection_contract.py`
- `tests/test_fige_metric_selection.py`
- `.github/workflows/fige-metric-selection-contract-smoke.yml`

## Fail-closed behavior

The selector rejects:

- another company identity;
- a different or incomplete 2021-2025 year window;
- insufficient observations for a selected metric;
- non-diagnostic upstream audit evidence;
- upstream evidence claiming PIT eligibility;
- duplicate contract metric/concept names;
- non-contiguous required years;
- scoring fields inside the selection contract.

Reported zero remains a valid numerical observation. Missing metrics remain unavailable
and cannot silently satisfy the contract.

## Live smoke

The workflow rebuilds the official CVM 2021-2025 economic audit, then evaluates the
selection contract against that newly collected evidence.

It fails if:

- required candidate evidence disappears;
- a primary candidate becomes empirically saturated;
- scoring/routing becomes active in this block;
- the peer-count block disappears unexpectedly.

Both the upstream economic-audit JSON and the metric-selection JSON are uploaded for
artifact inspection.

## Next evidence block

Do **not** invent thresholds from FIGE's own history and do **not** lower the structural
engine's peer requirement just to make one issuer rankable.

The next FIGE block is to identify whether a defensible set of current Brazilian listed
companies shares the same **non-prudential financial economic/accounting profile**.
Identity and accounting semantics must be verified exactly; sector labels or company
names alone are insufficient.

Possible outcomes are deliberately open:

1. a defensible comparable peer set exists, allowing model calibration work;
2. fewer than eight but multiple defensible peers exist, requiring an explicit design
   decision on confidence/shrinkage backed by evidence;
3. FIGE is economically too idiosyncratic for cross-sectional structural scoring, in
   which case the correct behavior may be explicit abstention rather than a fabricated
   sector score.

Only after that peer-evidence block should the project create scoring directions,
weights/thresholds, routing, remove FIGE from the applicability-review registry, and
run the mandatory scoring/backtest regression comparison.
