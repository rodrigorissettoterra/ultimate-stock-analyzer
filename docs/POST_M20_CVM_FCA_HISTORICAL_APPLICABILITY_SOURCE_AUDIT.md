# Post-M20 — CVM FCA historical model-applicability source audit

Status: **diagnostic source audit; no historical route or readiness promotion**.

## Objective

Determine whether historical CVM Formulário Cadastral (FCA) archives contain structured,
point-in-time-capable evidence that can support an issuer's historical **project model family**.

This block follows the FRE audit. The bounded structured FRE evidence exposed filing timing and
version lineage but no activity-like field, so FCA is inspected as the next official free source.

## Official-source contract

The CVM open-data FCA dataset states that the complete form content is published in structured CSV
files and that annual archives are updated weekly with eventual re-presentations. Historical annual
ZIPs are available from 2010 onward.

The audit uses the existing official CVM collector and does not modify the shared collector contract.
For every requested archive it records:

- exact source URL, byte size and SHA-256;
- every CSV member and its complete header schema;
- bounded issuer-row counts;
- issuer identity resolved directly by `CD_CVM` when available or through CNPJ linkage otherwise;
- applicability-like candidate fields and bounded sample values;
- filing-availability timing candidates;
- reporting/reference-period metadata separately;
- revision/version metadata separately.

## Candidate discovery

Applicability discovery is deliberately broad but non-promoting. Header tokens include concepts such
as activity, sector, CNAE, line of business, segment, corporate purpose, classification, category,
issuer type and nature.

A header match is **not** a model mapping. It only tells us what semantic validation to perform next.

Publication timing is stricter: reference-period fields such as `DT_REFER` are never accepted as
proof that evidence was public. Only receipt, delivery or publication-like fields can satisfy
`filing_timing_fields_found`.

## Bounded live sample

The live workflow inspects FCA delivery years 2024 and 2025 for:

- Petrobras — CVM 9512;
- Vale — CVM 4170;
- Itaú Unibanco — CVM 19348.

The sample intentionally spans prospective general-corporate and bank routes. It does not establish
a universal mapping rule.

## Fail-closed blockers

```text
FCA_APPLICABILITY_FIELD_UNAVAILABLE
FCA_ISSUER_COVERAGE_INCOMPLETE
FCA_FILING_TIMING_FIELDS_UNPROVEN
FCA_APPLICABILITY_TO_MODEL_MAPPING_UNPROVEN
HISTORICAL_MODEL_APPLICABILITY_UNPROVEN
```

The last two remain active throughout this discovery block even if promising fields are found.
`sector_routing_point_in_time_ready=false` and `readiness_promotion_allowed=false` are invariant.

## Decision after the live artifact

If the FCA artifact exposes stable activity/classification fields plus filing timing, the next block
must validate exact field semantics and deterministic mapping into `HistoricalModelRoute` records for
specific company-years before the fundamental accounting contract is selected.

If FCA also lacks defensible applicability evidence, the project should stop searching indefinitely:
strict historical evaluation will instead use explicit abstention for company-years without an
admissible route, while current B3 classification remains current-state evidence only.
