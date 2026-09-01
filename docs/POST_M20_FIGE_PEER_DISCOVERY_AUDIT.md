# Post-M20 — FIGE Comparable Peer Discovery Audit

## Status

This block is diagnostic only. It starts after the FIGE accounting contract, economic
metric audit and metric-selection contract have been validated.

It does **not** approve a `financial_non_prudential` peer set, change score formulas or
weights, alter routing, remove FIGE from the applicability-review registry, or change
rankings/backtests.

## Objective

The FIGE metric-selection contract requires at least eight comparable companies before
the existing cross-sectional structural scorer can be considered. The contract currently
contains only exact FIGE identity `cvm:6041`.

This block asks whether the current Brazilian-company B3 universe contains issuers close
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

## Classification scopes

FIGE is discovered dynamically as the anchor. Other eligible issuers are grouped as:

- `EXACT_SEGMENT`: same B3 sector, subsector and segment;
- `SAME_SUBSECTOR`: same B3 sector and subsector, different segment;
- `SAME_SECTOR`: same sector only.

Only exact-segment and same-subsector companies still on the fallback model proceed to
DFP schema inspection. Same-sector companies are context only. Issuers already routed to
a specialized structural model are excluded before FIGE schema matching.

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
the potential count including FIGE. Regardless of the result, this block keeps:

- `peer_set_ready=false`;
- `scoring_ready=false`;
- `routing_ready=false`;
- `applicability_registry_resolvable=false`.

If the current B3 subsector cannot even reach eight schema-compatible candidates, that is
evidence against forcing FIGE into the existing cross-sectional scorer. A later design may
need an idiosyncratic or abstaining model rather than an artificially broadened peer set.

## Live smoke

```bash
python scripts/fige_peer_discovery_audit.py \
  --year 2025 \
  --output fige-peer-discovery-audit.json
```

The workflow `.github/workflows/fige-peer-discovery-audit-smoke.yml` publishes the JSON
artifact for manual inspection.

Transient B3/CVM network failures should be handled by rerunning the same SHA. Do not
weaken source validation or business logic merely to make an external network failure green.
