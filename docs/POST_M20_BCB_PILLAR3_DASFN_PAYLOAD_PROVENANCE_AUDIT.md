# Post-M20 — BCB Pillar 3 DASFN institution payload provenance audit

Status: diagnostic only; no historical-readiness promotion.

## Goal

The central DASFN catalog snapshot is now complete and discovery-ready for the
current catalog. This block moves one layer deeper: it probes a deterministic
set of institution-hosted Pillar 3 payloads referenced by the official central
`URLDados` values and records transport/content provenance without treating
current reachability as point-in-time evidence.

The objective is to separate four questions that must not be conflated:

1. does an old-reference payload URL still respond today?;
2. does the response expose a usable JSON payload?;
3. is there authoritative publication-time evidence for that payload?;
4. is there a revision/vintage mechanism capable of reproducing what was known
   at a historical as-of timestamp?

Only the first two can be observed by this live audit. Questions 3 and 4 remain
blocked until stronger official evidence exists.

## Deterministic sample

The live script uses four Brazilian banks relevant to the analyzer:

- Banco do Brasil — CNPJ `00000000000191`;
- Itaú Unibanco — CNPJ `60701190000104`;
- Banco Bradesco — CNPJ `60746948000112`;
- Banco Santander (Brasil) — CNPJ `90400888000142`.

For each institution it selects a year-end KM1 resource for reference years
2022 and 2025, producing eight expected institution-year samples.

The central snapshot remains the source of truth for the exact `URLDados`.
The script additionally constrains each selected URL to the previously observed
institution host for that CNPJ. A row that does not match the expected host is
not probed.

## Network-safety boundary

Institution-hosted `URLDados` is treated as third-party input even though it is
published by the BCB central catalog.

The payload client therefore uses `follow_redirects=False`.

A redirect is preserved as HTTP evidence but is not followed. This prevents an
institution-controlled redirect from turning the live audit into an SSRF path.
Catalog traversal uses a separate client because the catalog URL is fixed to the
official BCB endpoint and its final URL is independently validated by the
snapshot audit.

Each payload body is bounded to 2 MB in the live workflow, with a hard CLI
maximum of 5 MB. A response that exceeds the bound is marked incomplete and is
not trusted as usable payload evidence.

## Evidence recorded

For each observed sample the audit records:

- institution CNPJ;
- reference year;
- DASFN version and resource template;
- exact central `URLDados` and requested URL;
- final URL;
- HTTP status and content type;
- selected response headers, including `Date`, `Last-Modified`, `ETag`,
  `Content-Length`, `Cache-Control`, and `Location` when present;
- SHA-256 and byte size;
- whether the body was captured completely;
- whether the response is trusted HTTP evidence;
- whether the body is usable JSON;
- observed JSON field names and revision-like field names;
- whether an old-reference payload is reachable now.

No response body is committed to the repository. The workflow publishes only the
bounded audit report as a short-retention GitHub Actions artifact.

## Fail-closed interpretation

The following observations are deliberately *not* accepted as PIT proof:

- an HTTP `Last-Modified` header is not automatically the payload's original
  publication timestamp;
- an ETag is not a revision history;
- a date encoded in a URL is a reference-period hint, not historical-vintage
  lineage;
- timestamp/version-like JSON fields are observations until their semantics are
  documented and proven;
- institution-catalog `dataUltimaAtualizacao` describes catalog update timing,
  not necessarily publication timing of an individual payload;
- the fact that a 2022 URL responds in 2026 proves current reachability only, not
  that today's bytes are identical to what was available in 2022.

Therefore these blockers remain invariant in this block:

- `BANK_EVIDENCE_NOT_POINT_IN_TIME`;
- `PILLAR3_DASFN_PAYLOAD_PUBLICATION_TIMESTAMP_UNPROVEN`;
- `PILLAR3_DASFN_REVISION_HISTORY_UNPROVEN`;
- `PILLAR3_DASFN_HISTORICAL_VINTAGE_QUERY_UNPROVEN`.

Additional probe blockers can include:

- `PILLAR3_DASFN_PAYLOAD_SAMPLE_MISSING`;
- `PILLAR3_DASFN_PAYLOAD_UNAVAILABLE`;
- `PILLAR3_DASFN_PAYLOAD_FINAL_URL_UNTRUSTED`;
- `PILLAR3_DASFN_PAYLOAD_BODY_INCOMPLETE`;
- `PILLAR3_DASFN_PAYLOAD_JSON_UNUSABLE`.

The audit always keeps:

- `payload_publication_timestamp_proven=false`;
- `revision_history_proven=false`;
- `historical_vintage_query_proven=false`;
- `historical_replay_ready=false`;
- `bank_evidence_point_in_time_ready=false`;
- `readiness_promotion_allowed=false`.

## Implementation

This block adds:

- `src/ultimate_stock_analyzer/backtesting/bcb_pillar3_dasfn_payload_provenance_audit.py`;
- `tests/test_bcb_pillar3_dasfn_payload_provenance_audit.py`;
- `scripts/bcb_pillar3_dasfn_payload_provenance_audit.py`;
- `.github/workflows/bcb-pillar3-dasfn-payload-provenance-audit-smoke.yml`;
- this document.

Report effect:

`diagnostic_only_pillar3_payload_provenance_no_readiness_change`

Schema version: `0.1`.

## Next evidence step

Use the live artifact to determine which institution/resource/version families
actually expose timing or lineage hints. Then investigate only those concrete
contracts for authoritative semantics or historical addressing. No bank field may
be promoted to point-in-time admissible solely from this diagnostic audit.
