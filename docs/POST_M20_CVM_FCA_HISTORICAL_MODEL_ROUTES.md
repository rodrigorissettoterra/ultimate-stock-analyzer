# Post-M20 — CVM FCA historical model-route materialization

Status: **explicit PIT route materialization; no historical readiness promotion in this block**.

## Objective

Convert exact, versioned FCA applicability filings into immutable `HistoricalModelRoute` records without reconstructing historical B3 taxonomy and without using the project registry's default fallback as evidence.

## Explicit mapping rule

`config/backtesting/fca_model_routes_v0.1.yml` is the source of truth for this block. It pins both its own rule version and the expected project sector-registry version.

Initial proven labels:

| CVM FCA `Setor_Atividade` | Project model |
| --- | --- |
| `Bancos` | `banks` |
| `Petróleo e Gás` | `commodities` |
| `Extração Mineral` | `commodities` |

Unknown FCA labels **abstain**. They are never sent through the `general_corporate` default as a historical inference.

Before materialization, every configured label is run through `SectorModelRegistry`. The materializer fails if:

- the pinned sector-registry version differs;
- the current registry selects a different model;
- the selection is a fallback.

This prevents a historical mapping file from silently drifting away from the scoring registry.

## Evidence contract

For each exact FCA filing, the route binds:

- canonical `cvm:<CD_CVM>` identity;
- fiscal year from `Data_Referencia`;
- explicit project model ID;
- conservative filing `available_from` from the FCA ledger;
- `CVM_FCA` as evidence source;
- exact document ID/version lineage;
- a route SHA-256 combining the filing evidence hash, mapping-file SHA-256, mapping-rule version, sector-registry version, FCA sector label and selected model.

If multiple observed filings exist for one company-year and all map to the same model, the earliest proven `available_from` is retained. Conflicting model families, unmapped labels, non-PIT filing evidence or a blocked input ledger fail closed for that route set.

## Bounded live expectation

The dedicated smoke uses official FCA 2024/2025 archives and expects:

- Vale 2024 → `commodities`, available 2024-12-03;
- Petrobras 2024 → `commodities`, available 2024-07-26;
- Itaú 2024 → `banks`, available 2024-08-17;
- Vale 2025 → `commodities`, available 2025-04-12;
- Petrobras 2025 → `commodities`, available 2025-05-16;
- Itaú 2025 → `banks`, available 2025-03-12.

All six routes must remain PIT eligible and evidence-hashed.

## Safety boundary

This block does not alter `FundamentalCoverageProfiler`, bootstrap manifests, historical readiness or M16 weights. The next block will persist these routes beside the already preserved raw FCA annual archives and make the profiler choose the accounting contract from the historical route before considering any current B3 classification.
