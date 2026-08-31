# Post-M20 — Current-state pre-scoring universe gate

## Objective

Provide a reusable, fail-closed integration seam that applies the validated Brazilian-company issuer-jurisdiction contract **before** investment scoring.

This block prevents foreign, conflicting or unresolved CVM identities from entering cross-sectional peer normalization in a current Brazilian-company equity analysis.

## Important production boundary

The repository does not currently contain a production job that calculates and persists the modern `IntegratedDecision` objects consumed by the API. The runtime worker currently performs repository-readiness maintenance, while the API is a read/query layer over persisted analyses.

Therefore this block is intentionally described as an **integration seam**, not as a claim that a production ranking job is already wired end to end.

## Gate contract

`partition_current_analysis_rows(...)` requires every input row to contain the canonical issuer identity:

`company_id = cvm:<CD_CVM>`

It consumes a previously constructed `BrazilianEquityEligibilityReport` and returns:

1. eligible analysis rows, preserving their input fields;
2. an audit report with row counts, status counts and exact excluded-row diagnostics.

Ticker is retained only as a diagnostic label. It is never used to establish eligibility.

## Fail-closed behavior

The gate raises instead of guessing when:

- an analysis row has no `company_id`;
- `company_id` does not follow the canonical CVM format;
- an input company has no corresponding eligibility decision.

Known decisions with these statuses are excluded before scoring and retained in diagnostics:

- `EXCLUDED_FOREIGN_ISSUER`;
- `CONFLICTING_CVM_REGISTRY_CLASSIFICATION`;
- `UNRESOLVED_CVM_REGISTRY_CLASSIFICATION`.

Only `ELIGIBLE_BRAZILIAN_PUBLIC_COMPANY` rows proceed.

## Scoring integration seam

`AnalyzerService.rank_current_brazilian_equities(...)` demonstrates the required ordering:

`raw current rows -> universe gate -> scoring engine`

The legacy `AnalyzerService.rank(...)` method remains unchanged for backward compatibility and synthetic examples.

The gate is engine-agnostic so the future modern integrated calculation pipeline can apply the same contract before structural, peer-relative or integrated ranking calculations.

## Point-in-time limitation

The current CVM public-company and foreign-issuer registries are current-state evidence. Consequently the gate report is permanently marked:

- `scope = CURRENT_STATE_ONLY`;
- `point_in_time_eligible = false`.

This method must not be used to reconstruct historical backtest universes. Historical eligibility requires separately validated point-in-time jurisdiction evidence.

## Non-effects

This block does not change:

- any score formula;
- scoring weights or thresholds;
- existing structural/integrated `rankable` formulas;
- API query filtering;
- backtesting or walk-forward logic;
- the behavior of the existing generic `AnalyzerService.rank(...)` method.
