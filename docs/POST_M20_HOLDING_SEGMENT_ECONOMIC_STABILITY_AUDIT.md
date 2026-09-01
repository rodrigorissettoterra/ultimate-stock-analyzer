# Post-M20 — Holding Segment Economic Stability Audit

## Status

Diagnostic only. This block follows the merged ITSA peer-discovery audit, which found four current eligible Brazilian-equity issuers in ITSA's exact B3 segment (`Holdings Diversificadas`) and showed that all three non-ITSA candidates preserve the seven `itsa_holding_cvm_v1` bindings in DFP 2025.

This audit does **not** create a holding score, threshold, peer set, routing rule, rankability change, recommendation change, valuation rule or applicability-registry resolution.

## Objective

Test whether the **current exact B3 segment members** show stable holding-accounting structure and economically holding-like composition across DFP 2021–2025 before any segment-level abstention route is considered.

The current member set is discovered dynamically from official B3/CVM identity data at runtime. No company name, ticker or CVM code other than the ITSA anchor is hardcoded into the historical audit.

Current B3 classification is used only to define today's diagnostic cohort; it is not projected backward as point-in-time historical classification.

## Evidence model

For every current exact-segment member and every fiscal year 2021–2025, the audit records:

- whether individual BPA/BPP/DRE statement evidence exists;
- exact coverage of the seven `itsa_holding_cvm_v1` bindings;
- exact coverage of the five critical concepts;
- missing, label-mismatched and ambiguous concepts;
- exact values for available contract concepts;
- descriptive economic ratios.

The five critical concepts are:

- `total_assets`;
- `investments_total`;
- `equity`;
- `equity_method_result`;
- `net_income_parent`.

Missing evidence remains UNKNOWN. No missing account or year is converted to zero, and no fuzzy account-name remapping is allowed.

## Parent/child protection

The investment tree is intentionally not aggregated by summing every matching row. `investments_total` uses exact parent `BPA 1.02.02`; supporting child rows are reported independently.

This avoids double counting nested `Participações Societárias` / `Outros Investimentos` rows.

## Descriptive metrics

The audit publishes, when denominators are valid:

- `investments_to_assets`;
- `equity_to_assets`;
- `equity_method_to_net_income`;
- `equity_investments_to_investments`;
- `other_investments_to_investments`.

For each current segment member it also summarizes observation count, minimum, maximum and median for every metric across the requested window.

These ranges are descriptive evidence only. This block intentionally defines **no** threshold that classifies an issuer as a holding or authorizes routing.

## Why this block is needed

The preceding peer discovery established two facts:

1. all four current exact-segment issuers are accounting-schema compatible in DFP 2025;
2. the segment contains only four companies, below the structural cross-sectional minimum of eight.

Therefore a defensible percentile-based holding score cannot be created inside this segment merely by reusing the current structural engine.

The remaining product question is different: whether the exact segment is sufficiently homogeneous in accounting structure and economic composition that applying ordinary `general_corporate` semantics is misleading for the cohort. This audit produces evidence for that later routing decision without making the decision itself.

## Fail-closed rules

- exact ITSA anchor identity is required;
- segment membership comes from the current eligible B3 classification snapshot;
- every member must share the anchor's exact sector, subsector and segment;
- annual CVM data is issuer-bounded by exact `CD_CVM`;
- exact statement + account code + label is required for schema evidence;
- missing annual DFP evidence remains explicitly missing;
- no current B3 classification is treated as historical PIT classification;
- `segment_routing_ready=false` regardless of results;
- `applicability_registry_resolvable=false` regardless of results.

## Live smoke

```bash
python scripts/holding_segment_economic_stability_audit.py \
  --start-year 2021 \
  --end-year 2025 \
  --output holding-segment-economic-stability-audit.json
```

The workflow `.github/workflows/holding-segment-economic-stability-audit-smoke.yml` publishes the JSON artifact for inspection.

## Decision boundary

A fully stable result would only justify a **separate** regression/routing block to test a holding-specific abstention model against the current universe. It would not justify a holding score, peer percentile, weight, threshold or historical backtest.

If the segment shows material economic heterogeneity or unstable critical accounting semantics, ITSA must remain unresolved until a narrower issuer-level or alternative absolute-evaluation design is supported by evidence.

## Temporal boundary

The audit uses current latest-state annual CVM DFP archives and the current B3 classification snapshot. These sources are appropriate for accounting-contract and current-routing research, but are not complete revision-aware point-in-time inputs for strict historical walk-forward backtests.
