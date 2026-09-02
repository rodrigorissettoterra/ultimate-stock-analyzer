# Post-M20 — CVM IPE Pillar 3 Filing Ledger Audit

Status: **diagnostic only; bank readiness unchanged**.

## Goal

The BCB IFData point-in-time audit proved initial publication timing but not historical revision
vintages. This block tests a different official path for bank prudential history: Pillar 3 reports
observed through the CVM IPE delivery ledger.

The target live sample is Itaú Unibanco Holding (`cvm:19348`) for annual prudential periods
2024-12-31 and 2025-12-31.

## Source contract

BCB Pillar 3 rules require periodic prudential disclosure and define publication deadlines. For the
period between the structured BCB Pillar 3 API generations, institutions disclosed reports through
their own published documents.

CVM IPE provides an official annual issuer-document index grouped by year of delivery. Its rows expose
issuer identity, reference date, delivery date, presentation type, delivery protocol, version and an
official RAD download URL. The current year and prior-year resources can receive updates and
re-presentations.

That makes IPE useful as an **observed filing ledger**, but not automatically a proof that every
historical revision is still represented.

## Audit contract

The diagnostic:

1. downloads each required official CVM IPE annual ZIP;
2. records source URL, SHA-256 and byte size;
3. filters strictly by canonical CVM identity;
4. identifies Pillar 3 candidates only from explicit metadata text;
5. maps explicit quarter tokens such as `4T24` to prudential quarter-end dates;
6. preserves every mapped filing in delivery order, including protocol and version;
7. reports periods with multiple observed filings without interpreting them as a proven complete
   revision chain.

Availability continues to use the conservative CVM IPE rule already present in the project:
`Data_Entrega + 1 day at 00:00 UTC`.

## Fail-closed boundaries

This block always retains:

```text
BANK_EVIDENCE_NOT_POINT_IN_TIME
PILLAR3_IPE_REVISION_HISTORY_COMPLETENESS_UNPROVEN
PILLAR3_PDF_CONTENT_UNVALIDATED
PILLAR3_PRUDENTIAL_METRIC_COVERAGE_UNPROVEN
```

Missing requested periods, ambiguous/missing period tokens and missing RAD URLs add their own blockers.

Therefore the following remain false:

```text
revision_history_completeness_proven
pdf_content_validated
prudential_metric_coverage_proven
historical_prudential_source_ready
bank_evidence_point_in_time_ready
readiness_promotion_allowed
```

Finding two filings for one period is useful evidence of re-presentation behavior. It is not enough to
claim that the IPE archive is a complete revision-vintage source.

## Live smoke

The workflow downloads the official 2025 and 2026 IPE archives, validates their provenance and requires
at least one mapped official filing for both 4T24 and 4T25. It does not require multiple filings because
that is an empirical observation, not a source-contract guarantee.

The evidence artifact is:

```text
cvm-ipe-pillar3-filing-ledger-evidence
```

## Next step

If the live artifact provides usable filing timelines, the next separate block may download/hash the
official RAD documents and validate Pillar 3 PDF content and prudential metric coverage. No bank PIT
blocker can be removed before document content, metric semantics and revision behavior are defensible.
