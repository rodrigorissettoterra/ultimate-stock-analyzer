# Post-M20 — BCB Pillar 3 DASFN unfiltered catalog snapshot audit

Status: diagnostic only; no historical-readiness promotion.

## Goal

Audit the current central BCB DASFN `Recursos` catalog without relying on the
server-side `Api=pilar3` filter, which is currently returning HTTP 400. The audit
uses documented OData pagination and performs the Pillar 3 selection locally.

## Collection contract

The implementation uses the exact official `Recursos` endpoint with:

- no `$filter`;
- `$format=json`;
- `$select=Api,Versao,CnpjInstituicao,Recurso,URLDados`;
- fixed `$top` and contiguous `$skip`;
- exact final-URL/query preservation;
- whole-page SHA-256 and HTTP/transport provenance.

The CLI remains conservative by default at 500 rows × 20 pages (10,000 rows).
The live verification workflow intentionally uses an expanded bound of 500 rows ×
100 pages (50,000 rows) because the first live run reached the former 10,000-row
cap with a full final page. The expanded workflow is still bounded and requests
only the five central fields needed for the audit.

## First live observation

The initial 10,000-row run remained correctly fail-closed as
`PILLAR3_DASFN_CATALOG_SNAPSHOT_INCOMPLETE`. Within those first 10,000 central
rows it observed:

- 9,473 Pillar 3 rows;
- 245 institutions;
- versions `1.2.0`, `2.0.0`, and `2.0.1`;
- both v1 and v2 version families;
- 109 distinct resource templates.

Those observations are discovery evidence only. They do not prove that the
10,000-row prefix represented the complete central catalog.

## Central contract before local filtering

Every collected row must provide non-empty:

- `Api`;
- `Versao`;
- `CnpjInstituicao`;
- `Recurso`;
- `URLDados`.

`CnpjInstituicao` must contain 14 digits. Structural validation applies to the
whole collected catalog before local `Api=pilar3` selection is considered usable.

Selected Pillar 3 rows must belong strictly to the recognized `1`/`1.x` or
`2`/`2.x` version families. Unknown families such as `10.x` block the local
selection rather than being ignored.

## Snapshot completeness

A snapshot is complete only when:

- every page is a trusted HTTP success;
- every non-final page contains exactly `$top` rows;
- the final page contains fewer than `$top` rows.

Reaching the configured page cap with a full last page remains
`PILLAR3_DASFN_CATALOG_SNAPSHOT_INCOMPLETE`, regardless of how many usable rows
were observed.

## Fail-closed PIT boundary

The invariant blockers remain:

- `BANK_EVIDENCE_NOT_POINT_IN_TIME`;
- `PILLAR3_DASFN_HISTORICAL_VINTAGE_QUERY_UNPROVEN`;
- `PILLAR3_DASFN_PAYLOAD_PUBLICATION_TIMESTAMP_UNPROVEN`;
- `PILLAR3_DASFN_REVISION_HISTORY_UNPROVEN`;
- `PILLAR3_DASFN_STRUCTURED_COVERAGE_GAP`.

A successful current snapshot never changes:

- `historical_vintage_query_proven=false`;
- `historical_replay_ready=false`;
- `bank_evidence_point_in_time_ready=false`;
- `readiness_promotion_allowed=false`.

## Next evidence step

Once a complete current snapshot is observed within the expanded bound, select a
small deterministic institution/resource sample from central `URLDados` values
and audit institution-hosted payload provenance. That audit must separately prove
publication timing, revision lineage, historical addressability, and contract
scope before any Pillar 3 field can become point-in-time admissible.
