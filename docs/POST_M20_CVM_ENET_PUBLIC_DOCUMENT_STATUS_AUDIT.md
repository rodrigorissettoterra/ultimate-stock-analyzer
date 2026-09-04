# Post-M20 — CVM ENET public document-status audit

Status: diagnostic only; no bank point-in-time readiness promotion.

## Goal

The CVM IPE annual archives already preserve delivery dates, presentation type,
delivery protocol, version and official RAD URLs. Live evidence for Itaú shows
both v1 presentations and later v2 spontaneous re-presentations for the same
Pillar 3 reference periods.

That proves an observed version sequence. It does not by itself prove the
historical state of a document after CVM/RAD actions such as cancellation or
blocking.

This block probes the public ENET external-consultation grid as a separate source
of document-status evidence.

## Public source

The public page is:

`https://www.rad.cvm.gov.br/ENETWeb/frmConsultaExternaCVM.aspx`

The live grid uses the page WebMethod `ListarDocumentos`. The method path is
handled as an empirically validated public web contract, not as a stable or
formally versioned API. The live smoke must prove the current response envelope
before the PR can merge.

Expected response fields are the ASP.NET WebMethod envelope `d` containing at
least:

- `temErro`;
- `expirouSessao`;
- `msgErro`;
- `dados`.

The audit never treats undocumented flattened-row delimiters as a durable source
contract. It hashes the flattened payload and extracts only bounded semantic
signals needed for this diagnostic.

## Deterministic live sample

The sample targets Itaú Unibanco Holding (`cvm:19348`) and the four exact delivery
dates already proven by the official IPE ledger:

- 2025-02-05 — 4T24 v1 presentation;
- 2025-03-31 — 4T24 v2 spontaneous re-presentation;
- 2026-02-04 — 4T25 v1 presentation;
- 2026-03-31 — 4T25 v2 spontaneous re-presentation.

Each request covers exactly one calendar day and uses `Pilar 3` as the public-grid
keyword. It deliberately does not depend on an undocumented server-side company
selector. Target CVM identity is validated locally from the returned grid text,
including common zero/hyphen formatting variants.

## Security and collection boundary

- only the fixed official `rad.cvm.gov.br` / `www.rad.cvm.gov.br` HTTPS host is
  accepted;
- redirects are not followed;
- the public page is fetched first only to establish the public session;
- each POST response is capped at 2 MB;
- oversized responses are incomplete evidence;
- no credentials, CAPTCHA bypass, browser automation or private endpoint is used;
- no raw ENET response is committed to the repository;
- the workflow artifact contains hashes, counts and extracted semantic tokens.

## What this audit can prove

If the current public contract succeeds, the audit can establish that the public
grid currently exposes status semantics for the same delivery dates represented
in the IPE filing ledger. It records recognized status, modality and version-like
tokens when present.

This is stronger than relying only on the current annual ZIP, because the public
grid explicitly exposes a Status column.

## What it cannot prove yet

A current Status value is not the historical action timeline.

The diagnostic therefore keeps the distinction between:

1. **observed filing/version sequence** — already evidenced by annual IPE rows;
2. **current public document status** — target of this block;
3. **historical document-action timeline** — still required to reproduce whether
   a filing was available, blocked or cancelled at a historical as-of timestamp.

Consequently these blockers remain:

- `BANK_EVIDENCE_NOT_POINT_IN_TIME`;
- `PILLAR3_IPE_REVISION_HISTORY_COMPLETENESS_UNPROVEN`;
- `PILLAR3_IPE_DOCUMENT_ACTION_HISTORY_UNPROVEN`.

Additional live-contract blockers include:

- `PILLAR3_IPE_ENET_PUBLIC_QUERY_UNAVAILABLE`;
- `PILLAR3_IPE_ENET_PUBLIC_CONTRACT_UNUSABLE`;
- `PILLAR3_IPE_ENET_TARGET_DOCUMENT_NOT_OBSERVED`;
- `PILLAR3_IPE_ENET_FINAL_URL_UNTRUSTED`;
- `PILLAR3_IPE_ENET_RESPONSE_TOO_LARGE`.

The audit always leaves:

- `historical_action_timeline_proven=false`;
- `revision_history_completeness_proven=false`;
- `bank_evidence_point_in_time_ready=false`;
- `readiness_promotion_allowed=false`.

## Next step

If the public probe succeeds, split the existing generic revision blocker into a
formal version-sequence proof and an action-history proof. The IPE ledger can then
prove contiguous observed re-presentations independently, while ENET/RAD evidence
is investigated for historical status/action timing. Only an exact scoped proof
of both may contribute to Pillar 3 point-in-time admissibility.
