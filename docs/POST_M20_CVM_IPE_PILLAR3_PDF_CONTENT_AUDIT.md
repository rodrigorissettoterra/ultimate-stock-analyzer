# Post-M20 — CVM IPE Pillar 3 PDF Content Audit

Status: **diagnostic only; bank readiness unchanged**.

## Goal

The prior CVM IPE filing-ledger audit observed version 1 and an explicit spontaneous
re-presentation (version 2) for Itaú Pillar 3 4T24 and 4T25. This block follows those exact official
RAD URLs and validates the underlying documents without treating the observed version chains as a
proof of global revision-history completeness.

## Validation contract

For every observed requested filing the live audit:

1. refetches the official annual CVM IPE archives and reconstructs the filing ledger;
2. downloads the exact official RAD document for its delivery protocol/version;
3. requires PDF magic bytes and parses the document with the open-source `pypdf` audit dependency;
4. records PDF SHA-256, byte size, page count, extracted-text SHA-256 and text length;
5. requires the expected prudential reference-period token in the extracted document;
6. requires KM1 evidence;
7. requires text evidence for the four bank capital metrics already used by the verified IFData
   contract: Capital Principal, Nível I, Índice de Basileia and Razão de Alavancagem. The Tier-I
   detector accepts the explicit Itaú wording and the fixed KM1 regulatory form `Índice de Nível 1`.

The audit does not infer numeric values from nearby strings. Numeric KM1 extraction is a separate
contract because table layout and value attribution require their own deterministic validation.

## Fail-closed separation

Successful PDF validation can prove:

```text
pdf_content_validated = true
prudential_metric_coverage_proven = true
```

for the exact observed versioned documents.

It cannot by itself prove that CVM IPE contains every historical version for every bank and period.
Therefore these remain unchanged:

```text
PILLAR3_IPE_REVISION_HISTORY_COMPLETENESS_UNPROVEN
BANK_EVIDENCE_NOT_POINT_IN_TIME
revision_history_completeness_proven = false
historical_prudential_source_ready = false
bank_evidence_point_in_time_ready = false
readiness_promotion_allowed = false
```

## Dependency boundary

`pypdf` is added only to the optional `audit` dependency group. Production/API containers do not need
PDF parsing merely because this diagnostic exists.

## Next step

If the live artifact validates every observed version, the next block can implement a deterministic
KM1 numeric parser and compare values across version 1/re-presentation timelines. Only after metric
values and the historical version contract are defensible can the project consider replacing
latest-state IFData capital ratios with version-aware Pillar 3 evidence in strict historical runs.
