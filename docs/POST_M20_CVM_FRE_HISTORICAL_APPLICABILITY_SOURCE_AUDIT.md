# Post-M20 — CVM FRE historical model-applicability source audit

Status: **diagnostic source audit; no sector-routing or readiness promotion**.

## Objective

Investigate whether official historical CVM Formulário de Referência (FRE) archives can provide
point-in-time evidence for this project's historical **model-family applicability**.

This is intentionally different from reconstructing B3 sector/subsector/segment taxonomy. The
public B3 classification workbook remains a current snapshot and is not retroactively applied.

## Official-source boundary

The CVM open-data portal exposes annual FRE archives from 2010 onward. The audit downloads the
official ZIP, fingerprints it, enumerates CSV members, restricts value inspection to requested CVM
issuer codes and discovers candidate structured fields without accepting their semantics in advance.

Three evidence categories are deliberately kept separate:

- **activity candidates**: headers related to activity, business, object, sector, segment, CNAE,
  products or services;
- **filing-date candidates**: actual receipt/delivery/reference/presentation date-like headers;
- **revision candidates**: version/protocol metadata.

A version number is not treated as publication timing. `filing_timing_fields_found=true` requires a
non-empty date-like field; revision metadata is reported separately.

## Bounded live sample

The smoke inspects delivery-year archives 2024 and 2025 for:

- Petrobras — CVM 9512;
- Vale — CVM 4170;
- Itaú Unibanco — CVM 19348.

These companies intentionally exercise different prospective model families. Their presence does
not establish a generic mapping rule.

## Fail-closed contract

The audit always keeps these claims separate:

1. a structured activity-like field exists;
2. a filing-date field exists and has values for the bounded issuers;
3. revision/version metadata exists;
4. the activity field semantics describe the issuer at the simulated date;
5. a deterministic mapping from that evidence to a project model family is valid;
6. none of these claims reproduces historical B3 taxonomy.

Until semantics, publication timing, revision behavior and deterministic mapping are validated,
`sector_routing_point_in_time_ready=false` and `readiness_promotion_allowed=false`.

Core blockers include:

```text
FRE_STRUCTURED_ACTIVITY_FIELD_UNAVAILABLE
FRE_ISSUER_COVERAGE_INCOMPLETE
FRE_FILING_TIMING_FIELDS_UNPROVEN
FRE_ACTIVITY_TO_MODEL_MAPPING_UNPROVEN
HISTORICAL_MODEL_APPLICABILITY_UNPROVEN
```

The mapping and historical-applicability blockers remain by design in this discovery block.

## Interpretation

A green workflow means the official source was inspected reproducibly and the audit failed closed
correctly. It does **not** remove `SECTOR_ROUTING_NOT_POINT_IN_TIME`.

If live evidence exposes useful activity plus actual filing dates, the next block should validate
their semantics and create explicit per-company-year `HistoricalModelRoute` records before the
fundamental coverage profiler chooses an accounting contract. If the evidence is insufficient,
strict historical runs should abstain for unproven company-years rather than inherit today's B3
classification.
