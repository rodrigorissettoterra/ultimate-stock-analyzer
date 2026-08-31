# Post-M20 — Current Brazilian listed-equity security eligibility

## Objective

Define a deterministic current-state **security-level** eligibility contract after separately validating issuer jurisdiction and the live FCA security-type distribution.

Issuer eligibility and security eligibility remain distinct contracts.

## Current eligible security contract

A security is eligible only when all conditions below hold:

1. its canonical `company_id = cvm:<CD_CVM>` has an eligible Brazilian public-company issuer decision;
2. the latest FCA row for `company_id + ticker` is active on the analysis date;
3. FCA administrator is exactly B3 after whitespace/case normalization;
4. FCA market is exactly `Bolsa` after whitespace/case normalization;
5. FCA `security_type` is one of:
   - `Ações Ordinárias`;
   - `Ações Preferenciais`;
   - `Units`.

Every condition is based on official structured data. Ticker suffixes, company names and fuzzy matching are forbidden.

## Why Units are included

The project universe is implemented as Brazilian **listed equity securities**, not only single-share certificates. Units issued by jurisdiction-eligible Brazilian public companies are exchange-traded equity packages and must not be silently lost simply because their FCA type is `Units` rather than an individual ON/PN share.

This wording is intentionally more precise than using “ações” as a synonym for every eligible ticker.

## Explicit exclusions

The current contract excludes:

- foreign issuers before security evaluation;
- securities outside their current trading bounds;
- securities whose FCA administrator is not B3;
- securities outside `Bolsa`;
- unsupported FCA types, including `Bônus de Subscrição`;
- jurisdiction-eligible issuers with no FCA security row;
- jurisdiction-eligible issuers whose FCA rows contain no security satisfying all eligibility conditions.

All exclusions remain diagnostic. They do not receive a negative investment score.

## Current-state boundary

FCA and current B3/CVM registries are latest-state evidence. Therefore this contract is marked:

- `scope = CURRENT_STATE_ONLY`;
- `point_in_time_eligible = false`.

It must not be used to reconstruct historical constituents or backtests. A historical security-universe contract requires point-in-time listing/security evidence.

## Integration boundary

This block defines and live-validates the security eligibility contract. It does not yet replace the issuer-level B3 coverage manifest or change scoring/rankability. A later integration block may feed only eligible security/company identities into the current pre-scoring universe gate while retaining issuer and security exclusion diagnostics separately.
