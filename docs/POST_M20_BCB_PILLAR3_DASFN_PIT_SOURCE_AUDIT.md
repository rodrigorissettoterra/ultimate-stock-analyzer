# Post-M20 — BCB Pillar 3 DASFN PIT source audit

Status: diagnostic only; no historical-readiness promotion.

## Goal

Audit the official BCB/DASFN structured Pillar 3 distribution contract before any
bank field is allowed to contribute point-in-time evidence to historical
backtests.

This block answers a narrow question: does the public structured source, as
currently evidenced, expose enough publication/revision/vintage semantics to
reconstruct what an investor could have known at a historical evaluation time?

It does **not** change `FundamentalCoverageProfiler`,
`HistoricalBacktestReadiness`, the bank field-evidence router, or any scoring
model.

## Official source contract

The audit is anchored to the official BCB sources:

- Pillar 3 v1 dataset:
  <https://dadosabertos.bcb.gov.br/dataset/pilar3>
- Pillar 3 v2 dataset:
  <https://dadosabertos.bcb.gov.br/dataset/pilar3-v2>
- DASFN catalog API documentation:
  <https://www.bcb.gov.br/htms/dasfn/catalogo/1.0.4/redoc.html>
- DASFN catalog OData endpoint:
  `https://olinda.bcb.gov.br/olinda/servico/DASFN/versao/v1/odata/Recursos`

The official BCB dataset pages establish these reference-date boundaries:

- structured Pillar 3 v1: reference dates through **2023-06-30**;
- structured Pillar 3 v2: reference dates from **2025-12-31**;
- reference dates strictly between those boundaries: institution disclosures in
  PDF, rather than the structured API.

The BCB also states that the underlying open-data payloads are stored and served
by the regulated institutions, while the BCB collects and catalogs the links
daily.

## What the live audit observes

The smoke workflow requests one raw DASFN catalog snapshot with
`Api eq 'pilar3'`. The original BCB response is preserved by SHA-256, byte size,
row count, and observed field names. The audit then groups that same snapshot
locally into version-family observations for v1 and v2.

For each version family it records:

- row count;
- observed `Versao` values;
- observed resource templates;
- path placeholders such as `semestre` and `trimestre`.

This design deliberately avoids pretending that client-side v1/v2 subsets are
independent live source responses. The provenance anchor remains the single raw
BCB catalog snapshot.

These observations establish current catalog provenance and the existence of
structured reference-period routes. They do not establish historical payload
vintages.

## Point-in-time boundary

A reference-period selector answers questions such as “which semester/quarter is
this report about?”. A historical vintage selector would instead need to answer
“which version of that report was available at time T?”. Those are different
contracts.

The catalog collection timestamp is likewise evidence that a link was observed
at collection time. It is not, by itself, a row/payload publication timestamp for
the institution-hosted report.

For that reason, this block remains fail-closed with:

- `BANK_EVIDENCE_NOT_POINT_IN_TIME`;
- `PILLAR3_DASFN_HISTORICAL_VINTAGE_QUERY_UNPROVEN`;
- `PILLAR3_DASFN_PAYLOAD_PUBLICATION_TIMESTAMP_UNPROVEN`;
- `PILLAR3_DASFN_REVISION_HISTORY_UNPROVEN`;
- `PILLAR3_DASFN_STRUCTURED_COVERAGE_GAP`.

Even if a catalog field name looks temporal or version-like, field naming alone
is not accepted as proof of revision-aware historical replay semantics.

## Implementation

Added in this block:

- `src/ultimate_stock_analyzer/backtesting/bcb_pillar3_dasfn_pit_source_audit.py`
- `tests/test_bcb_pillar3_dasfn_pit_source_audit.py`
- `scripts/bcb_pillar3_dasfn_pit_source_audit.py`
- `.github/workflows/bcb-pillar3-dasfn-pit-source-audit-smoke.yml`

The report effect is fixed to:

`diagnostic_only_pillar3_dasfn_pit_source_no_readiness_change`

and `readiness_promotion_allowed` remains `false`.

## What this block does not prove

It does not prove that:

1. an institution payload contains a trustworthy publication timestamp;
2. corrected/revised payloads remain historically addressable;
3. the API exposes an as-of/vintage selector;
4. all historical revisions can be reconstructed;
5. the PDF-only interval has been normalized into a strict PIT ledger;
6. any bank critical field is ready for historical-readiness promotion.

## Next evidence step

Use the DASFN catalog to select a bounded set of institution-hosted Pillar 3
resources and audit their actual payload contracts. The next block should test,
without promoting readiness, whether representative v1/v2 institution APIs expose
publication timestamps, immutable versions, revision ledgers, or an equivalent
mechanism that can reconstruct historical vintages.

Only after that evidence exists should the result be considered for
`bank_field_evidence_routing.py`, and only a later integration block should alter
coverage/readiness behavior.
