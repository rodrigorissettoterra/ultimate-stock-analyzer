# Post-M20 — Structural applicability review registry

## Objective

Keep economically suspicious `general_corporate` fallback cases visible and auditable without changing investment scores before the relevant model contracts are validated.

This registry is diagnostic only. It does **not** change sector routing, rankability, score components, weights, thresholds, vetoes, universe eligibility or integrated decisions.

## Canonical identity rule

Every review entry is keyed by the stable issuer identity:

`company_id = cvm:<CD_CVM>`

`issuer_code` is retained only as an operational B3 audit label. Ticker/name inference and fuzzy matching are not allowed.

## Review statuses

### `GENERAL_CORPORATE_MODEL_REVIEW_REQUIRED`

The issuer reaches the `general_corporate` fallback and has already passed the current Brazilian core-equity universe contracts, but its economic structure still requires explicit review before the fallback can be treated as the final specialized-model decision.

The status does not make the issuer non-rankeable by itself.

### `UNIVERSE_ELIGIBILITY_REVIEW_REQUIRED`

This status remains supported by the registry schema for future unresolved universe cases, but **no v0.2 active review uses it**. The deterministic issuer-jurisdiction and current B3 security-level universe contracts resolved the previous G2DI/PPLA cases.

## v0.2 active reviewed canonical issuers

- `cvm:6041` / `FIGE` — listed core-equity issuer; model applicability remains unresolved.
- `cvm:27634` / `B100` — listed core-equity issuer; model applicability remains unresolved.
- `cvm:7617` / `ITSA` — listed core-equity holding issuer; model applicability remains unresolved.

The active list is deliberately narrow. Other fallbacks remain valid diagnostic fallbacks unless separately audited and added by canonical identity.

## Resolved v0.1 entries

The following entries were intentionally removed from the active registry after later universe contracts supplied deterministic answers:

- `cvm:80195` / `G2DI` — resolved as `EXCLUDED_FOREIGN_ISSUER` by the CVM domestic/foreign issuer-jurisdiction contract.
- `cvm:80152` / `PPLA` — resolved as `EXCLUDED_FOREIGN_ISSUER` by the same contract.
- `cvm:18759` / `BSCS` — no longer a model-routing question in the current universe because the validated B3 security-level contract does not establish an eligible current ON/PN/Unit security for this issuer.

Removing these entries from the diagnostic model-review registry does not erase their audit trail; their resolution lives in the issuer/security universe contracts and associated post-M20 documentation/artifacts.

## Smoke-manifest behavior

The B3 coverage manifest reports:

- registry version and `diagnostic_only` effect;
- reviewed fallback count;
- counts and bounded `company_id` samples by review status;
- reviewed identities that no longer route to fallback (`review_non_fallback_company_ids`);
- reviewed identities absent from the current B3 classification snapshot (`review_unmatched_company_ids`).

The last two fields make registry drift visible rather than silently preserving stale assumptions.

## Next acceptance gate

The three remaining reviews are now **model questions**, not universe questions. Before any of them changes routing or scoring, a later block must validate the proposed economic model with:

1. explicit formula and applicability criteria;
2. authoritative/free-first data sources;
3. missing-data behavior;
4. tests and diagnostics;
5. point-in-time/backtest treatment where applicable.

Until then, `general_corporate` remains the operational fallback and the v0.2 registry remains diagnostic only.
