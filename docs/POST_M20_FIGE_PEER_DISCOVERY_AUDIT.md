# Post-M20 — FIGE Comparable Peer Discovery Audit

## Status

This block is diagnostic only. It starts after the FIGE accounting contract, economic
metric audit and metric-selection contract have been validated.

It does **not** approve a `financial_non_prudential` peer set, change score formulas or
weights, or change rankings/backtests. After explicit FIGE structural abstention exists,
this audit remains active as a peer-set drift monitor.

## Objective

The FIGE metric-selection contract requires at least eight comparable companies before
the existing cross-sectional structural scorer can be considered. The validated current
peer evidence initially contained only exact FIGE identity `cvm:6041`.

This audit asks whether the current Brazilian-company B3 universe contains issuers close
enough in classification and CVM accounting schema to justify a later multi-year economic
comparability audit. A schema match is only a discovery filter, not peer approval.

## Identity and universe boundary

The live audit reuses the official-source chain already present in the repository:

1. current B3 industry-classification workbook;
2. current B3 company catalog;
3. canonical `cvm:<CD_CVM>` identity;
4. CVM Brazilian public-company registry;
5. CVM foreign-issuer registry;
6. current Brazilian-company equity eligibility partition.

No ticker or company-name guessing is used. Current B3/CVM registry evidence remains
`point_in_time_eligible=false`.

## Anchor lifecycle

FIGE is discovered dynamically as the anchor. The audit accepts two intentional anchor
states:

- `general_corporate` while the economic-model review is unresolved;
- `financial_non_prudential_abstain` after the review is resolved by explicit structural
  abstention.

Any other FIGE model route fails closed and requires review.

## Classification scopes

Other eligible issuers are grouped as:

- `EXACT_SEGMENT`: same B3 sector, subsector and segment;
- `SAME_SUBSECTOR`: same B3 sector and subsector, different segment;
- `SAME_SECTOR`: same sector only.

Exact-segment and same-subsector companies proceed to DFP schema inspection when they are
on either the general fallback or the explicit non-prudential abstention route. The latter
is important for drift monitoring: a future issuer entering FIGE's segment will inherit the
safe abstention route but must still be inspected as a possible peer.

Same-sector companies are context only. Issuers routed to genuine specialized economic
models such as `banks` or `insurance` remain excluded before FIGE schema matching.

## DFP schema comparison

The smoke downloads the official 2025 DFP archive once and filters every audited issuer
by exact `CD_CVM` before normalization.

For each company the FIGE bindings are compared by statement, exact account code and exact
normalized account label. The FIGE anchor itself must continue to match all 16 bindings;
anchor schema drift fails closed.

History-validation candidacy requires exact availability of the concepts needed by the
three primary uncalibrated FIGE metrics:

- `total_assets`;
- `net_income`;
- `pretax_income`;
- `gross_financial_intermediation_result`;
- `other_operating_result`.

This is a semantic-availability gate, not a score threshold.

## Candidate disposition

A near-classification issuer can end as:

- `EXCLUDED_SPECIALIZED_MODEL`;
- `NO_DFP_EVIDENCE`;
- `SCHEMA_MISMATCH`;
- `PRIMARY_SCHEMA_COMPATIBLE_REQUIRES_HISTORY_VALIDATION`.

Broader same-sector issuers remain `CONTEXT_ONLY_BROADER_SCOPE`.

Even the schema-compatible disposition is not an approved peer. A later block must test
multi-year economic behavior under validated company-specific accounting semantics.

## Cross-sectional gate

The report carries the peer minimum from the FIGE metric-selection contract and publishes
the potential count including FIGE. Regardless of the result, peer discovery itself keeps:

- `peer_set_ready=false`;
- `scoring_ready=false`.

The audit may run after routing is resolved; its purpose then is to detect whether new
current-state evidence changes the peer-set conclusion, not to automatically activate a
score.

## Live smoke

```bash
python scripts/fige_peer_discovery_audit.py \
  --year 2025 \
  --output fige-peer-discovery-audit.json
```

The workflow `.github/workflows/fige-peer-discovery-audit-smoke.yml` publishes the JSON
artifact for manual inspection and continues to run when sector routing changes.

Transient B3/CVM network failures should be handled by rerunning the same SHA. Do not
weaken source validation or business logic merely to make an external network failure green.
