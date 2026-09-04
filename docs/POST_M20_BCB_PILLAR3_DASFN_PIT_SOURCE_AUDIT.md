# Post-M20 — BCB Pillar 3 DASFN PIT source audit

Status: diagnostic only; no historical-readiness promotion.

## Goal

Audit the official BCB/DASFN structured Pillar 3 distribution contract before any
bank field is allowed to contribute point-in-time evidence to historical
backtests.

This block separates three questions that must not be conflated:

1. is the official DASFN central `Recursos` endpoint queryable now from a trusted
   BCB origin?
2. does a successful central response strictly satisfy the BCB central-resource
   row contract for Pillar 3?
3. does any of that prove historical publication/revision/vintage semantics for
   the institution-hosted payloads?

Only the third question could eventually support historical-readiness promotion.
This block deliberately keeps that answer as **no**.

It does **not** change `FundamentalCoverageProfiler`,
`HistoricalBacktestReadiness`, the bank field-evidence router, or any scoring
model.

## Official source contract

The audit is anchored to:

- BCB Dados Abertos do Sistema Financeiro Nacional;
- Pillar 3 v1 dataset: `https://dadosabertos.bcb.gov.br/dataset/pilar3`;
- Pillar 3 v2 dataset: `https://dadosabertos.bcb.gov.br/dataset/pilar3-v2`;
- central DASFN catalog OData endpoint:
  `https://olinda.bcb.gov.br/olinda/servico/DASFN/versao/v1/odata/Recursos`.

The BCB production registry currently lists catalog specification `1.0.12` and
Pillar 3 v2 `2.0.1`, both in production from 2026-05-06. Pillar 3 v1 remains the
historical structured family through its documented cutoff.

The reference-date boundaries used by this audit remain:

- structured Pillar 3 v1: through **2023-06-30**;
- structured Pillar 3 v2: from **2025-12-31**;
- dates strictly between those boundaries: institution disclosures in PDF rather
  than the structured API.

That coverage gap is a separate blocker from catalog availability.

## Central Olinda rows are not institution catalog JSON

Two different representations exist and must not be mixed.

The central BCB Olinda `Recursos` list is the BCB-collected list of individual
resources exposed by regulated institutions. The central row contract used by
this audit requires non-empty:

- `Api`;
- `Versao`;
- `CnpjInstituicao`;
- `Recurso`;
- `URLDados`.

`URLConsulta` is a separate central field and is not required because catalog
history contains resources where it is absent.

The catalog JSON hosted by each institution is a different contract. It describes
institution metadata and datasets using structures such as dataset references,
base URLs and resource paths. A generic `Url` from that representation must not be
accepted as a substitute for central `URLDados`.

The audit therefore validates the representation it actually probes: the central
Olinda list. This distinction prevents a successful future BCB response from
being rejected merely because two DASFN schema layers were conflated.

## Why endpoint failure is evidence, not a test crash

Live validation on 2026-09-04 showed:

- a minimal central catalog request returns HTTP 200;
- the BCB-published Pillar 3 `Api eq 'pilar3'` filtered query returns HTTP 400.

The official BCB open-data resource links for Pillar 3 use the same Olinda filter
family. The audit therefore preserves the HTTP 400 as source-contract evidence
instead of probing undocumented alternative filter syntax until a 200 is found.

The audit performs two bounded probes:

- `base`: a minimal central catalog request;
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

## Successful central responses remain fail-closed

If the Pillar 3 query returns usable OData JSON from the trusted final origin, the
audit may record:

- observed central row fields;
- v1/v2 version-family rows;
- `Versao` values;
- resource templates;
- reference-period placeholders such as `semestre` and `trimestre`.

`catalog_contract_usable=true` is intentionally strict. Every returned row must:

- contain the required central fields listed above;
- identify `Api=pilar3`;
- expose a 14-digit `CnpjInstituicao`;
- belong entirely to a recognized `1`/`1.x` or `2`/`2.x` version family;
- contribute to a result in which both v1 and v2 families are observed.

Mixed payloads, missing central fields, malformed CNPJs, unknown version families
such as `10.x`, or institution-catalog `Url` in place of `URLDados` block the whole
central catalog contract rather than being silently ignored.

The resource placeholders identify a report reference period. They are not
historical as-of/vintage selectors. Likewise, observing a central catalog response
at collection time does not prove when an institution-hosted payload was published
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

- `src/ultimate_stock_analyzer/backtesting/bcb_pillar3_dasfn_pit_source_audit.py`;
- `tests/test_bcb_pillar3_dasfn_pit_source_audit.py`;
- `scripts/bcb_pillar3_dasfn_pit_source_audit.py`;
- `.github/workflows/bcb-pillar3-dasfn-pit-source-audit-smoke.yml`.

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

Because the server-side Pillar 3 filter is currently failing while the minimal
central endpoint remains available, the next diagnostic step is to audit a bounded
**unfiltered, paginated central snapshot** using documented OData `$top`/`$skip`,
then select `Api=pilar3` locally.

That next audit must remain current-catalog discovery only. A successful snapshot
must not be interpreted as historical publication/revision evidence, and it must
not change bank readiness. Only after institution payload-level publication and
revision lineage is proven should evidence be considered for
`bank_field_evidence_routing.py` or historical readiness.
