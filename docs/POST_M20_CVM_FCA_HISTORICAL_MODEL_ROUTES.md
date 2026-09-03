# Post-M20 — CVM FCA historical model-route materialization

Status: **explicit PIT route materialization; no historical readiness promotion in this block**.

## Objective

Convert exact, versioned FCA applicability filings into immutable `HistoricalModelRoute` records without reconstructing historical B3 taxonomy and without using the project registry's default fallback as evidence.

## Source-vocabulary translation

CVM FCA and the project sector registry do not use identical vocabularies. `config/backtesting/fca_model_routes_v0.2.yml` therefore defines an explicit, versioned translation rule. It does not pretend that an FCA label is itself a B3 classification.

Each rule binds:

- exact FCA `Setor_Atividade`;
- explicit target project model;
- which **actual FCA field** must independently produce a non-fallback matching selection in the pinned `SectorModelRegistry`.

Initial rules:

| FCA `Setor_Atividade` | Project model | registry probe source |
| --- | --- | --- |
| `Bancos` | `banks` | `sector_activity` (`Bancos`) |
| `Petróleo e Gás` | `commodities` | `sector_activity` (`Petróleo e Gás`) |
| `Extração Mineral` | `commodities` | `activity_description` (live bounded evidence: `Mineração`) |

For each filing, the probe uses the field value actually present in that filing. The value is sent through the registry's sector-token matcher only as a compatibility check. If it falls back or selects another model, that company-year abstains with `FCA_MODEL_ROUTE_REGISTRY_MISMATCH`.

This specifically avoids adding `Extração Mineral` to the scoring registry merely to make the historical route smoke pass.

## Mapping integrity

The mapping file pins sector-registry version `0.6.3`. Every target must be an explicit non-default model in that registry. Rules are frozen, stored as a tuple, duplicate FCA labels are prohibited, and the mapping-file SHA-256 is part of route evidence.

Unknown FCA sector labels abstain with `FCA_MODEL_ROUTE_SECTOR_UNMAPPED`. They are never sent to the `general_corporate` default.

## Evidence contract

For each exact FCA filing, the route binds:

- canonical `cvm:<CD_CVM>` identity;
- fiscal year from `Data_Referencia`;
- explicit project model ID;
- conservative filing `available_from` from the FCA ledger;
- `CVM_FCA` as evidence source;
- exact document ID/version lineage;
- a route SHA-256 combining the filing evidence hash, mapping-file SHA-256, mapping-rule version, sector-registry version, FCA sector label, registry-probe source/value and selected model.

If multiple observed filings exist for one company-year and all map to the same model, the earliest proven `available_from` is retained. Conflicting model families, unmapped labels, registry-probe mismatch, non-PIT filing evidence or a blocked input ledger fail closed.

## Bounded live expectation

The dedicated smoke uses official FCA 2024/2025 archives and expects:

- Vale 2024 → `commodities`, available 2024-12-03;
- Petrobras 2024 → `commodities`, available 2024-07-26;
- Itaú 2024 → `banks`, available 2024-08-17;
- Vale 2025 → `commodities`, available 2025-04-12;
- Petrobras 2025 → `commodities`, available 2025-05-16;
- Itaú 2025 → `banks`, available 2025-03-12.

All six routes must remain PIT eligible, evidence-hashed and free of registry-probe mismatches.

## Safety boundary

This block does not alter `FundamentalCoverageProfiler`, bootstrap manifests, historical readiness or M16 weights. The next block will persist these routes beside the already preserved raw FCA annual archives and make the profiler choose the accounting contract from the historical route before considering any current B3 classification.
