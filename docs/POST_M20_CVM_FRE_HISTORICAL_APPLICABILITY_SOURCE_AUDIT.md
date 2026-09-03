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

Four evidence categories are deliberately kept separate:

- **activity candidates**: headers related to activity, business, object, sector, segment, CNAE,
  products or services;
- **filing-timing candidates**: actual receipt, delivery or publication date-like headers that may
  establish when evidence became observable;
- **reference-period candidates**: reporting/reference dates such as `DT_REFER`; these describe the
  period represented by the filing and do **not** prove market availability;
- **revision candidates**: version/protocol metadata.

A reference date or version number is never treated as publication timing. `filing_timing_fields_found=true`
requires a non-empty receipt/delivery/publication-like field.

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
2. a filing-timing field exists and has values for the bounded issuers;
3. reporting/reference metadata exists;
4. revision/version metadata exists;
5. the activity field semantics describe the issuer at the simulated date;
6. a deterministic mapping from that evidence to a project model family is valid;
7. none of these claims reproduces historical B3 taxonomy.

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

## Live finding

The bounded 2024/2025 artifacts exposed issuer coverage, receipt dates (`DT_RECEB`), reference dates
(`DT_REFER`) and versions, but no structured activity-like field across the inspected FRE CSV
members. This means FRE remains useful for filing lineage/timing diagnostics but cannot by itself
materialize historical model-family routes from the structured archive observed here.

## Interpretation

A green workflow means the official source was inspected reproducibly and the audit failed closed
correctly. It does **not** remove `SECTOR_ROUTING_NOT_POINT_IN_TIME`.

Because the structured FRE evidence did not expose activity fields in the bounded live run, the next
source audit should inspect historical FCA evidence for an explicit issuer activity/classification
field. If no defensible historical source produces a model-family route, strict historical runs must
abstain for unproven company-years rather than inherit today's B3 classification.
