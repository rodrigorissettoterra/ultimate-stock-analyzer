# Post-M20 — B100 Accounting Lifecycle Audit

## Status

Diagnostic only. B100 (`cvm:27634`) is the last issuer in the current structural-applicability review registry after FIGE and ITSA were resolved by explicit abstention routes.

This block does **not** choose B100's structural model and does not change routing, scoring, rankability, valuation, recommendations or the applicability registry.

## Why lifecycle and scope matter

B100 has a short listed-company history. Official current public evidence shows that its CVM registration dates from September 2024 and B3 trading began in February 2025. Its disclosed activity is a holding of fiduciary-administration and asset-management services, while subsequent corporate-control/reorganization events make a single individual 2025 balance sheet an unsafe basis for a permanent economic-model decision.

The earlier generic holding audit exposed an unusual individual DFP 2025 snapshot with very small assets/equity relative to the reported period result. The correct next step is therefore to inspect accounting semantics through time and across consolidation scopes rather than infer a model from that one observation.

## Requested evidence

The live audit collects current latest-state CVM archives for:

- DFP 2024;
- DFP 2025;
- ITR 2026.

For each archive it evaluates both:

- `ind` — individual statements;
- `con` — consolidated statements.

BPA, BPP and DRE files are mandatory. DFC indirect/direct-method files are included when the exact corresponding archive file exists and their availability is recorded in the artifact.

For ITR 2026, the latest reference date present in the archive is used. No interim value is annualized or relabeled as a full-year number.

## Two independent accounting comparators

Each snapshot is evaluated separately against two existing evidence contracts.

### General corporate comparator

Exact fixed-account extraction is evaluated against `general_corporate_v1`, including critical coverage for assets, working-capital structure, equity, revenue/profit lines, taxes, parent net income and operating cash flow.

A high coverage result means the required ordinary-corporate concepts are available; it does **not** by itself prove that general-corporate economics are the right model.

### Holding-schema comparator

The same BPA/BPP/DRE tree is compared with the exact seven-account schema validated for ITSA holdings. This is a schema comparator only. B100 is not assumed to share ITSA's economic model merely because codes and labels match.

The artifact reports critical and total holding-schema coverage, exact concepts, missing concepts, label mismatches and ambiguities.

## Descriptive values

Where present, the audit exposes:

- total assets;
- total investments (`BPA 1.02.02`);
- equity;
- revenue;
- EBIT;
- equity-method result;
- net income;
- cash from operations;
- investments/assets;
- equity/assets;
- equity-method result/net income.

Missing values remain UNKNOWN. No absent line is represented as zero.

## Fail-closed rules

- exact issuer identity must be `cvm:27634` / `CD_CVM=27634`;
- required BPA/BPP/DRE archive files must exist for each requested document/scope;
- optional DFC file availability is explicitly detected and recorded;
- latest revision selection follows the existing CVM fixed-account/tree normalization contracts;
- general-corporate and holding evidence remain independent;
- zero evidence across all requested snapshots fails the live smoke;
- partial or contradictory evidence does **not** fail merely because it leaves B100 unresolved;
- `routing_ready=false`, `scoring_ready=false`, `applicability_registry_resolvable=false` regardless of results.

## Live smoke

```bash
python scripts/b100_accounting_lifecycle_audit.py \
  --output b100-accounting-lifecycle-audit.json
```

The workflow `.github/workflows/b100-accounting-lifecycle-audit-smoke.yml` publishes the complete JSON artifact for review.

## Decision boundary

After the live artifact is inspected:

- if the current consolidated business consistently supports ordinary-corporate semantics, a later regression block may explicitly resolve B100 to `general_corporate`;
- if the accounting/economic structure is holding-like but not safely scoreable, a later issuer-specific abstention block may be justified;
- if lifecycle/scope evidence remains contradictory, B100 stays in the applicability review registry.

No threshold or automatic classifier in this block makes that decision.

## Temporal boundary

Current CVM DFP/ITR archives are latest-state snapshots, not complete revision-aware point-in-time datasets. They support current accounting-model research but are not treated as strict historical walk-forward evidence.
