# Post-M20 — Current B3 universe partition

## Objective

Integrate the validated Brazilian-company jurisdiction contract into the current B3 coverage manifest without changing investment scoring or historical eligibility.

The manifest now keeps two distinct views:

1. the existing raw mapped B3 classification/model coverage for audit continuity;
2. the current Brazilian-company-eligible subset after canonical CVM jurisdiction resolution.

## Identity and jurisdiction

B3 classification identity remains:

`workbook issuer code -> official B3 company catalog -> codeCVM -> company_id`

Jurisdiction then compares the canonical `company_id = cvm:<CD_CVM>` against:

- `CVM_CAD` — Brazilian public-company registry;
- `CVM_FOREIGN_ISSUER_CAD` — foreign-issuer registry.

No ticker suffix, issuer-name inference or fuzzy matching is used.

## Partition behavior

Mapped B3 records are partitioned into:

- `ELIGIBLE_BRAZILIAN_PUBLIC_COMPANY`;
- `EXCLUDED_FOREIGN_ISSUER`;
- `CONFLICTING_CVM_REGISTRY_CLASSIFICATION`;
- `UNRESOLVED_CVM_REGISTRY_CLASSIFICATION`.

Only the first group enters `eligible_brazilian_equity_model_coverage`.

Foreign, conflicting and unresolved records remain visible through bounded `(issuer_code, company_id)` audit samples. They are not assigned negative scores and are not silently discarded.

A B3 classification record without a corresponding universe decision is treated as a pipeline consistency error and fails closed.

## Backward-compatible raw coverage

The existing top-level `report` is preserved unchanged in meaning: it reports all B3 classification records that resolve through the official current B3 company catalog, plus the separately audited outside-catalog issuer-code cases.

The new `current_brazilian_equity_universe` is a second-stage partition of the mapped canonical identities. This separation prevents jurisdiction filtering from rewriting historical identity coverage metrics.

## Point-in-time limitation

The current B3 classification, current CVM public-company registry and current CVM foreign-issuer registry are all treated as current-state evidence in this gate.

Therefore the partition is `point_in_time_eligible = false` through the parent manifest and must not be used to reconstruct historical backtest universes.

## Non-effects

This block does not alter:

- structural scores;
- `rankable` in the structural engine;
- weights or thresholds;
- integrated decision logic;
- historical walk-forward/backtest eligibility.

A later pipeline-integration block may use the validated eligible subset before scoring, but only for current analysis and while preserving exclusion audit output.
