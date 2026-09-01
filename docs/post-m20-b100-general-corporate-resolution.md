# Post-M20 — B100 General-Corporate Applicability Resolution

## Decision

B100 (`cvm:27634`) remains on the existing `general_corporate` default structural route. No specialized model and no issuer-specific abstention route are introduced.

The only state transition in this block is removal of B100 from the diagnostic structural-applicability review queue. Registry v0.5 therefore contains no unresolved model-review entries.

## Evidence chain

The resolution follows three separate evidence blocks rather than a single accounting snapshot:

1. the B100 lifecycle audit compared DFP 2024, DFP 2025 and ITR 2026 across individual and consolidated scopes;
2. that audit showed the parent/individual company is holding-like while consolidated DFP 2025 and current consolidated ITR 2026 both provide complete `general_corporate_v1` critical-account coverage and do not provide the complete ITSA holding critical schema;
3. the fixed-account extractor was then corrected globally to prefer consolidated CVM statements whenever available and to use individual statements only as an explicit fallback, preventing cross-scope account mixing.

The structural model is intended to represent the economic listed group. Under the corrected extraction contract, the consolidated evidence therefore supports retaining B100 on `general_corporate`.

## What is not changing

This block does not alter:

- `sector_registry_v0.6.yml`;
- any structural scoring config;
- B100's selected model id (`general_corporate`);
- B100's fallback status or peer-group mechanics;
- metric directions, targets, tolerances, category weights or ranking thresholds;
- valuation, recommendation or portfolio logic;
- FIGE or ITSA abstention routing.

## Live regression contract

The resolution smoke must prove all of the following against the current eligible Brazilian-company B3 universe:

- exactly one current eligible classification exists for `cvm:27634`;
- B100 selects `general_corporate` with `default_fallback` before and after the diagnostic registry transition;
- removing the B100 review produces zero routing deltas across the eligible universe;
- sector-model counts, fallback/specialized counts and ambiguity state are invariant;
- v0.4 contains exactly the prior B100 fallback review and v0.5 contains no reviews;
- reviewed fallback count moves from one to zero;
- consolidated DFP 2025 has 100% general-corporate critical coverage;
- consolidated ITR 2026 has 100% general-corporate critical coverage;
- neither consolidated snapshot has 100% ITSA holding critical-schema coverage.

Any failed condition leaves the resolution invalid.

## Why the individual holding-like presentation does not require abstention

B100's individual statements remain visible evidence and are not discarded. They describe the legal parent and can naturally be dominated by investments in subsidiaries. The structural scoring contract, however, uses consolidated statements when they exist so that operating subsidiaries are represented in group-level fundamentals. The individual presentation is therefore not, by itself, evidence that the listed group must abstain from ordinary corporate structural metrics.

## Current review registry

`config/universe/b3_structural_applicability_reviews_v0.5.json` is intentionally empty. Earlier registry versions remain immutable evidence of the sequence by which BSCS, foreign issuers, FIGE, ITSA and finally B100 were resolved.

## Temporal boundary

B3 industry classification and CVM annual/interim archives used by the live regression are current/latest-state evidence. They are not revision-aware point-in-time history and must not be retroactively applied as historical routing labels in walk-forward backtests.
