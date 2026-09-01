# Post-M20 — ITSA Issuer-Specific Structural Abstention

## Status

Validated routing design for ITSA (`cvm:7617`) only. The model is an explicit structural **abstention**, not a holding score.

## Why issuer identity is required

The evidence chain established:

- ITSA has a stable holding accounting contract across DFP 2021–2025;
- its exact B3 segment has only four current eligible companies, below the structural cross-sectional minimum of eight;
- all four companies share the same seven-account schema in 2025;
- the historical economic audit nevertheless shows material heterogeneity inside the segment, especially ARANDU, whose investment share is far below ITSA's.

Therefore a segment-wide holding route would over-capture economically different issuers. The narrowest supported rule is exact canonical CVM identity.

## Registry contract

`SectorModelRegistry` now supports optional `match.company_ids` entries. They are exact canonical `cvm:<CD_CVM>` matches; they are not substring matches and they require the caller to propagate `company_id`.

The ITSA rule is:

```yaml
- id: itsa_holding_abstain
  priority: 110
  config: sectors/itsa_holding_abstain_v0.6.yml
  peer_group_by: []
  match:
    company_ids: [cvm:7617]
```

The config has no categories, metrics, directions, weights, targets, tolerances or score thresholds.

## Expected structural result

Even if a row contains extreme ordinary-corporate metrics, ITSA must remain:

- model: `itsa_holding_abstain`;
- model family: `itsa_holding_abstain_v1`;
- structural score: neutral engine default `50.0`;
- data coverage: `0.0`;
- confidence: `0.0`;
- `rankable=false`;
- no categories;
- flags including `NO_STRUCTURAL_DATA`, low coverage and low confidence.

The neutral numeric placeholder is not an investment opinion and is never rankable.

## Live regression gates

The current eligible Brazilian-equity B3 universe is evaluated twice: once with the ITSA definition removed from the same registry and once with the current registry.

The regression fails unless:

- the routing delta contains exactly `cvm:7617`;
- ITSA changes from `general_corporate` fallback to `itsa_holding_abstain`;
- the abstention model contains exactly ITSA in the current eligible universe;
- no issuer matches multiple specialized models;
- ITSA is absent from the current structural-applicability review registry;
- exact-segment neighbors such as ARND, EPAR and SIMH are not captured by the ITSA model;
- changing ordinary corporate metrics cannot change the abstention result.

## Applicability registry

`b3_structural_applicability_reviews_v0.4.json` preserves prior registries as historical evidence and removes ITSA only after the issuer-specific regression gate is introduced. B100 remains unresolved.

## Temporal boundary

The routing decision is supported by current B3/CVM identity plus latest-state historical accounting diagnostics. Current B3 classification is not revision-aware point-in-time evidence, so this block does not retroactively apply today's route in historical backtests.

## Non-effects

This block does not create a holding percentile, lower the minimum peer count, broaden the peer group, alter valuation, or modify the primary `AnalyzerService` recommendation engine. It changes only structural-model routing for the canonical ITSA issuer.
