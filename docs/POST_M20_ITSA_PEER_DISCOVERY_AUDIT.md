# Post-M20 — ITSA Comparable Peer Discovery Audit

## Status

Diagnostic only. This block starts after `itsa_holding_cvm_v1` has been validated and
merged. It does not create a holding score or change ITSA routing.

## Objective

Determine whether ITSA has a defensible current cross-sectional peer set inside its exact
B3 economic segment before any holding-specific structural score is considered.

The anchor is exact canonical identity `cvm:7617`. Candidate companies come dynamically
from the current eligible Brazilian-equity B3 classification universe and must share the
same exact:

- sector;
- subsector;
- segment.

No peer ticker or company name is hardcoded.

## Why exact segment first

The merged ITSA evidence shows a business model dominated by equity investments and equity-
method earnings. Broadening comparison to unrelated financial companies merely to reach a
numerical peer threshold would weaken economic comparability.

The diagnostic therefore begins with the narrowest official B3 classification that
captures diversified holdings. A broader scope would require a separate evidence block,
not an implicit fallback.

## Current model threshold

The audit reads the structural config selected for the ITSA anchor and uses that config's
`default_min_peer_count`. It does not duplicate the threshold in peer-discovery code.

At the current project state ITSA is still routed to `general_corporate`, whose minimum is
8 companies.

Two gates are reported independently:

1. **numerical gate** — can the entire exact B3 segment, before schema filtering, even
   reach the selected model's minimum?;
2. **schema gate** — how many exact-segment companies preserve all five critical concepts
   from `itsa_holding_cvm_v1` by exact statement + account code + label?

Passing the schema gate is not peer approval. It only creates a candidate for later
multi-year economic validation.

## Accounting-schema comparison

Every exact-segment candidate is inspected against the seven ITSA accounting bindings.
The five critical concepts are:

- `total_assets`;
- `investments_total`;
- `equity`;
- `equity_method_result`;
- `net_income_parent`.

A candidate becomes `CRITICAL_SCHEMA_COMPATIBLE_REQUIRES_HISTORY_VALIDATION` only when all
five critical concepts match exactly. Supporting investment-tree concepts may remain
missing without being silently imputed.

A mismatch in code, label or ambiguity is exposed; no fuzzy semantic remapping is used.

## Routing independence

Current sector-model selection is attached to every candidate as diagnostic metadata only.
It does **not** remove exact-segment candidates. This makes the audit useful even after a
future holding-specific route is introduced: a comparable issuer cannot silently disappear
from peer monitoring merely because its current model assignment changed.

## Decision boundary

Regardless of live results, this block keeps:

- `peer_set_ready=false`;
- `scoring_ready=false`;
- `routing_ready=false`;
- `applicability_registry_resolvable=false`.

If the exact segment contains fewer companies than the current minimum of the selected
structural model, the cross-sectional design is numerically impossible in that scope even
if every candidate has a perfect accounting-schema match. The system must not broaden the
peer group or lower the threshold merely to manufacture a score.

## Live smoke

```bash
python scripts/itsa_peer_discovery_audit.py \
  --year 2025 \
  --output itsa-peer-discovery-audit.json
```

The workflow `.github/workflows/itsa-peer-discovery-audit-smoke.yml` publishes the current
B3/CVM evidence artifact.

## Temporal boundary

B3 classification and issuer eligibility are current-state evidence. CVM annual DFP
archives are latest-state snapshots. This diagnostic is not point-in-time eligible for
historical backtests.
