# Post-M20 — BCB Pillar 3 DASFN PIT source audit

Status: diagnostic only; no historical-readiness promotion.

## Goal

Audit the official BCB/DASFN structured Pillar 3 distribution contract before any
bank field is allowed to contribute point-in-time evidence to historical
backtests.

This block separates three questions that must not be conflated:

1. is the official DASFN catalog endpoint queryable now from a trusted BCB origin?
2. does a successful catalog response strictly satisfy the documented Pillar 3
   v1/v2 resource contract?
3. does any of that prove historical publication/revision/vintage semantics for
   the institution-hosted payloads?

Only the third question could eventually support historical-readiness promotion.
This block deliberately keeps that answer as **no**.

It does **not** change `FundamentalCoverageProfiler`,
`HistoricalBacktestReadiness`, the bank field-evidence router, or any scoring
model.

## Official source contract

The audit is anchored to:

- Pillar 3 v1 dataset:
  <https://dadosabertos.bcb.gov.br/dataset/pilar3>
- Pillar 3 v2 dataset:
  <https://dadosabertos.bcb.gov.br/dataset/pilar3-v2>
- DASFN catalog API documentation:
  <https://www.bcb.gov.br/htms/dasfn/catalogo/1.0.4/redoc.html>
- DASFN catalog OData endpoint:
  `https://olinda.bcb.gov.br/olinda/servico/DASFN/versao/v1/odata/Recursos`

The documented reference-date boundaries remain:

- structured Pillar 3 v1: through **2023-06-30**;
- structured Pillar 3 v2: from **2025-12-31**;
- dates strictly between those boundaries: institution disclosures in PDF rather
  than the structured API.

## Why endpoint failure is evidence, not a test crash

Earlier live smokes demonstrated that the official Olinda `Recursos` endpoint can
return HTTP 400 for catalog queries. A source-contract audit must preserve that
observation rather than guessing alternative query syntax until one happens to
return HTTP 200.

The audit therefore performs two bounded probes:

- `base`: a minimal catalog request;
- `pillar3_query`: the documented Pillar 3 catalog filter.

For every probe it preserves:

- requested URL;
- final URL when an HTTP response exists;
- HTTP status;
- content type;
- SHA-256 and byte size of the response body;
- transport-error details when no HTTP response exists.

HTTP 4xx/5xx and network failures become explicit blockers while still producing
a complete diagnostic artifact.

## Trusted final-origin boundary

A raw HTTP 2xx is not enough to mark the BCB catalog as available. Because the
live client follows redirects, source availability requires both:

1. an HTTP 2xx response; and
2. a final URL that remains under `https://olinda.bcb.gov.br/`.

A 2xx response whose final URL leaves the official Olinda host remains preserved
as HTTP evidence, but it is not accepted as source availability. The audit adds
`PILLAR3_DASFN_FINAL_URL_UNTRUSTED` and continues fail-closed.

This prevents a redirect, proxy, captive portal, or unrelated third-party response
from being mistaken for BCB source evidence.

## Successful catalog responses remain fail-closed

If the Pillar 3 query returns usable OData JSON from the trusted final origin, the
audit may record:

- observed catalog fields;
- v1/v2 version-family rows;
- `Versao` values;
- resource templates;
- reference-period placeholders such as `semestre` and `trimestre`.

`catalog_contract_usable=true` is intentionally strict. Every returned row must:

- contain non-empty `Api`, `Versao`, `Recurso`, and `Url` fields;
- identify `Api=pilar3`;
- belong entirely to a recognized `1`/`1.x` or `2`/`2.x` version family;
- contribute to a result in which both v1 and v2 families are observed.

Mixed payloads, missing required fields, unknown families such as `10.x`, or
otherwise malformed rows block the whole catalog contract rather than being
silently ignored alongside valid rows.

The resource placeholders identify a report reference period. They are not
historical as-of/vintage selectors. Likewise, observing a catalog response at
collection time does not prove when an institution-hosted payload was published
or revised.

## Point-in-time boundary

The invariant blockers are:

- `BANK_EVIDENCE_NOT_POINT_IN_TIME`;
- `PILLAR3_DASFN_HISTORICAL_VINTAGE_QUERY_UNPROVEN`;
- `PILLAR3_DASFN_PAYLOAD_PUBLICATION_TIMESTAMP_UNPROVEN`;
- `PILLAR3_DASFN_REVISION_HISTORY_UNPROVEN`;
- `PILLAR3_DASFN_STRUCTURED_COVERAGE_GAP`.

Dynamic source-contract blockers are added when applicable:

- `PILLAR3_DASFN_CATALOG_ENDPOINT_UNAVAILABLE`;
- `PILLAR3_DASFN_PILAR3_QUERY_UNAVAILABLE`;
- `PILLAR3_DASFN_CATALOG_CONTRACT_UNUSABLE`;
- `PILLAR3_DASFN_VERSION_FAMILY_NOT_OBSERVED`;
- `PILLAR3_DASFN_FINAL_URL_UNTRUSTED`.

`readiness_promotion_allowed` remains `false` in every path.

## Implementation

Added in this block:

- `src/ultimate_stock_analyzer/backtesting/bcb_pillar3_dasfn_pit_source_audit.py`
- `tests/test_bcb_pillar3_dasfn_pit_source_audit.py`
- `scripts/bcb_pillar3_dasfn_pit_source_audit.py`
- `.github/workflows/bcb-pillar3-dasfn-pit-source-audit-smoke.yml`

The report effect is fixed to:

`diagnostic_only_pillar3_dasfn_pit_source_no_readiness_change`

Schema version: `0.4`.

## What this block does not prove

It does not prove that:

1. an institution payload contains a trustworthy publication timestamp;
2. corrected/revised payloads remain historically addressable;
3. the API exposes an as-of/vintage selector;
4. all historical revisions can be reconstructed;
5. the PDF-only interval has a strict PIT ledger;
6. any bank critical field is ready for historical-readiness promotion.

## Next evidence step

When a usable official catalog route is observable, select a bounded set of
institution-hosted Pillar 3 resources and audit the payload contracts themselves.
If the catalog remains unavailable, first identify an officially documented BCB
route that replaces the current Olinda contract; do not promote or infer data from
an undocumented workaround.

Only after payload-level publication/revision evidence exists should the result be
considered for `bank_field_evidence_routing.py`, and only a later integration
block should alter coverage/readiness behavior.
