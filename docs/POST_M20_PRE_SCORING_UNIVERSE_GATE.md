# Post-M20 — Current-state pre-scoring universe gate

## Objective

Provide a reusable, fail-closed integration seam that applies both validated current-universe controls **before** investment scoring:

1. Brazilian-company issuer jurisdiction by canonical CVM identity;
2. current B3 core-equity security eligibility by exact canonical company/security pair.

This prevents foreign, conflicting or unresolved CVM identities and non-core/unresolved B3 instruments from entering cross-sectional peer normalization in current Brazilian-equity analysis.

## Important production boundary

The repository does not currently contain a production job that calculates and persists the modern `IntegratedDecision` objects consumed by the API. The runtime worker currently performs repository-readiness maintenance, while the API is a read/query layer over persisted analyses.

Therefore this remains an **integration seam**, not a claim that a production ranking job is already wired end to end.

## Gate contract

`partition_current_analysis_rows(...)` always requires every input row to contain:

`company_id = cvm:<CD_CVM>`

With only `BrazilianEquityEligibilityReport`, the helper preserves its original issuer-only behavior for compatibility.

When `CurrentBrazilianEquitySecurityUniverseReport` is also supplied, every row must additionally contain an exact B3 security code in `ticker`. Eligibility is then established only by the exact pair:

`(company_id, ticker)`

No ticker suffix, issuer name, trading name or fuzzy matching is used.

The function returns:

1. eligible analysis rows, with canonicalized `company_id` and normalized uppercase `ticker`;
2. an audit report with row counts, status counts and exact excluded-row diagnostics.

## Fail-closed behavior

The gate raises instead of guessing when:

- an analysis row has no `company_id`;
- `company_id` does not follow the canonical CVM format;
- an input company has no corresponding issuer eligibility decision;
- security-level gating is requested but the row has no exact `ticker`;
- security-level gating is requested but the canonical company has no company decision in the current security-universe report.

Issuer-level exclusions remain diagnostic, including:

- `EXCLUDED_FOREIGN_ISSUER`;
- `CONFLICTING_CVM_REGISTRY_CLASSIFICATION`;
- `UNRESOLVED_CVM_REGISTRY_CLASSIFICATION`.

After issuer eligibility passes, security-level exclusions can include the statuses defined by the current B3 security contract, such as:

- `EXCLUDED_NON_CORE_SECURITY_KIND`;
- `EXCLUDED_NO_CURRENT_SPOT_TRADE`;
- `EXCLUDED_UNKNOWN_SECURITY_KIND`;
- `EXCLUDED_SECURITY_TAXONOMY_CONFLICT`;
- `EXCLUDED_SECURITY_CODE_IDENTITY_CONFLICT`.

A row whose ticker has no exact decision for the canonical company is excluded as `EXCLUDED_SECURITY_NOT_IN_CURRENT_UNIVERSE` rather than inferred from ticker format.

## Scoring integration seam

`AnalyzerService.rank_current_brazilian_equities(...)` now requires both reports and enforces:

`raw current rows -> issuer-jurisdiction gate -> exact B3 security gate -> scoring engine`

Therefore an otherwise eligible Brazilian issuer cannot reach scoring through a bonus, right, receipt, BDR, TPR, unresolved code or other non-core instrument.

The legacy `AnalyzerService.rank(...)` method remains unchanged for backward compatibility and synthetic examples.

## Current live-universe basis

The security report consumed by the method is built from the separately validated current-universe contract using:

- canonical CVM issuer identity and jurisdiction;
- exact B3 company/security identity from B3 company detail evidence;
- current-year B3 COTAHIST spot-market trading evidence;
- reviewed B3 `ESPECI` taxonomy, where ON, PN and Units are core equity.

The live validation preceding this integration produced 313 eligible Brazilian companies and 410 eligible ON/PN/Unit codes from 357 candidate B3 issuer identities. Those numbers are observations, not hard-coded scoring thresholds.

## Point-in-time limitation

The current CVM public-company/foreign-issuer registries and current B3 security/trading evidence are current-state controls. Consequently the gate report remains permanently marked:

- `scope = CURRENT_STATE_ONLY`;
- `point_in_time_eligible = false`.

This method must not be used to reconstruct historical backtest universes. Historical security eligibility requires separately validated point-in-time listing and instrument evidence.

## Non-effects

This integration does not change:

- any score formula;
- scoring weights or thresholds;
- existing structural/integrated `rankable` formulas;
- API query filtering;
- backtesting or walk-forward logic;
- the behavior of the existing generic `AnalyzerService.rank(...)` method.
