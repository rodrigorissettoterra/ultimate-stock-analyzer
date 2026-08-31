# Post-M20 — Structural applicability review registry

## Objective

Keep economically suspicious `general_corporate` fallback cases visible and auditable without changing investment scores before the relevant universe/model contracts are validated.

This block is diagnostic only. It does **not** change sector routing, rankability, score components, weights, thresholds, vetoes, or integrated decisions.

## Canonical identity rule

Every review entry is keyed by the existing stable issuer identity:

`company_id = cvm:<CD_CVM>`

`issuer_code` is retained only as an operational B3 audit label. Ticker/name inference and fuzzy matching are not allowed.

## Review statuses

### `GENERAL_CORPORATE_MODEL_REVIEW_REQUIRED`

The issuer currently reaches the `general_corporate` fallback, but the post-M20 economic audit found enough structural doubt that the fallback must not be treated as a permanently validated model choice without further evidence.

The status does not make the issuer non-rankeable by itself.

### `UNIVERSE_ELIGIBILITY_REVIEW_REQUIRED`

The issuer must remain visible while the project defines a deterministic security-type eligibility contract for the Brazilian-equity universe.

The status is not equivalent to exclusion and cannot remove an issuer/security from ranking by itself.

## v0.1 reviewed canonical issuers

- `cvm:6041` / `FIGE` — model applicability review.
- `cvm:18759` / `BSCS` — model applicability review.
- `cvm:27634` / `B100` — model applicability review.
- `cvm:7617` / `ITSA` — model applicability review.
- `cvm:80195` / `G2DI` — universe eligibility review.
- `cvm:80152` / `PPLA` — universe eligibility review.

The list is deliberately narrow. Other fallbacks remain valid diagnostic fallbacks unless separately audited and added by canonical identity.

## Smoke-manifest behavior

The B3 coverage manifest reports:

- registry version and `diagnostic_only` effect;
- reviewed fallback count;
- counts and bounded `company_id` samples by review status;
- reviewed identities that no longer route to fallback (`review_non_fallback_company_ids`);
- reviewed identities absent from the current B3 classification snapshot (`review_unmatched_company_ids`).

The last two fields make registry drift visible rather than silently preserving stale assumptions.

## Next acceptance gate

Before any review status can affect ranking, a later block must separately validate one of the following:

1. a deterministic security-type universe rule based on official security-master fields; or
2. a specialized structural/accounting model with formula, source, sector applicability, missing-data behavior, tests and point-in-time/backtest evidence.

Until then, the registry remains diagnostic only.
