# Post-M20 — BCB Pillar 3 DASFN unfiltered catalog snapshot audit

Status: diagnostic only; no historical-readiness promotion.

## Goal

When the official central Olinda server-side filter for `Api=pilar3` returns HTTP 400,
the project still needs a bounded, auditable way to determine whether the current
central DASFN catalog exposes Pillar 3 resources.

This block performs a current-catalog snapshot using only documented OData
pagination and projection:

- endpoint: `DASFN/versao/v1/odata/Recursos`;
- no `$filter`;
- `$select=Api,Versao,CnpjInstituicao,Recurso,URLDados`;
- fixed `$top`;
- contiguous `$skip`;
- bounded maximum page count;
- local `Api=pilar3` selection only after every collected row satisfies the
  central-resource structural contract.

It remains a discovery audit. It does not make bank evidence point-in-time ready.

## Why this is separate from the filtered-source audit

The preceding source-contract audit established two facts:

1. the minimal central `Recursos` endpoint can be reachable;
2. the BCB-published server-side `Api eq 'pilar3'` query can fail independently.

That failure must not be worked around by inventing undocumented filter syntax.
A bounded unfiltered traversal is a different, documented operation and therefore
gets its own audit and provenance.

## Minimal-data boundary

The live script deliberately avoids collecting unnecessary central catalog fields.
It requests only:

- `Api`;
- `Versao`;
- `CnpjInstituicao`;
- `Recurso`;
- `URLDados`.

The default live bound is 500 rows × 20 pages = at most 10,000 rows.

No institution contact data is requested.

## Page trust contract

Every input page must:

- target the exact official BCB DASFN `Recursos` endpoint;
- request `$format=json`;
- request the exact bounded `$select`;
- use the page metadata's `$top` and `$skip`;
- contain no `$filter`;
- contain no unsupported query parameters;
- form a contiguous sequence beginning at `skip=0`.

An HTTP 2xx response is trusted only if the final URL preserves the same endpoint
and the same `$format/$select/$top/$skip` contract. Redirects that add a filter,
change pagination, leave the endpoint, or introduce unsupported parameters are
preserved as evidence but are not trusted.

For every page the audit stores HTTP/transport provenance including SHA-256 and
body size when a response exists.

## Snapshot completeness

A snapshot is complete only when:

- every page is a trusted HTTP success;
- every non-final page contains exactly `$top` rows;
- the final page contains fewer than `$top` rows.

A full last page at the configured `max-pages` limit is not treated as complete.
The audit adds `PILLAR3_DASFN_CATALOG_SNAPSHOT_INCOMPLETE`.

## Central contract before local filtering

The whole traversed catalog must satisfy the minimum central row contract before
the local Pillar 3 result can be called discovery-ready.

Every row must provide non-empty:

- `Api`;
- `Versao`;
- `CnpjInstituicao`;
- `Recurso`;
- `URLDados`.

`CnpjInstituicao` must contain 14 digits.

This requirement applies even to non-Pillar-3 rows. A malformed row could
otherwise hide relevant data and make an incomplete/ambiguous traversal look
healthy.

## Local Pillar 3 selection

Only after structural validation does the audit select rows where
`Api.casefold() == "pilar3"`.

Selected rows must use recognized `1`/`1.x` or `2`/`2.x` version families.
Unknown families such as `10.x` block local-filter usability instead of being
silently ignored.

The audit exposes current observations including versions, resources and
institution CNPJs. These are discovery evidence only.

## Fail-closed PIT boundary

The following blockers remain invariant:

- `BANK_EVIDENCE_NOT_POINT_IN_TIME`;
- `PILLAR3_DASFN_HISTORICAL_VINTAGE_QUERY_UNPROVEN`;
- `PILLAR3_DASFN_PAYLOAD_PUBLICATION_TIMESTAMP_UNPROVEN`;
- `PILLAR3_DASFN_REVISION_HISTORY_UNPROVEN`;
- `PILLAR3_DASFN_STRUCTURED_COVERAGE_GAP`.

Additional snapshot blockers include:

- `PILLAR3_DASFN_CATALOG_PAGE_UNAVAILABLE`;
- `PILLAR3_DASFN_CATALOG_SNAPSHOT_INCOMPLETE`;
- `PILLAR3_DASFN_CATALOG_SNAPSHOT_CONTRACT_UNUSABLE`;
- `PILLAR3_DASFN_LOCAL_FILTER_NO_ROWS`;
- `PILLAR3_DASFN_LOCAL_FILTER_ROW_UNUSABLE`;
- `PILLAR3_DASFN_SNAPSHOT_FINAL_URL_UNTRUSTED`.

Even a fully successful current snapshot keeps:

- `historical_vintage_query_proven=false`;
- `historical_replay_ready=false`;
- `bank_evidence_point_in_time_ready=false`;
- `readiness_promotion_allowed=false`.

## Implementation

This block adds:

- `src/ultimate_stock_analyzer/backtesting/bcb_pillar3_dasfn_catalog_snapshot_audit.py`;
- `tests/test_bcb_pillar3_dasfn_catalog_snapshot_audit.py`;
- `scripts/bcb_pillar3_dasfn_catalog_snapshot_audit.py`;
- `.github/workflows/bcb-pillar3-dasfn-catalog-snapshot-audit-smoke.yml`;
- this document.

Report effect:

`diagnostic_only_dasfn_unfiltered_snapshot_no_readiness_change`

Schema version: `0.1`.

## Next evidence step

If current Pillar 3 rows are discovered, the next step is a bounded
institution-payload audit using the central `URLDados` values. That audit must
prove, separately:

1. payload publication timing;
2. revision lineage/history;
3. historical addressability or another strict as-of mechanism;
4. consolidation/contract compatibility for the target bank field.

Only after those are proven may any Pillar 3 observation contribute to
`BankFieldEvidenceRoutingReport` as `POINT_IN_TIME_ADMISSIBLE`.
