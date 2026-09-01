# Post-M20 — Current Brazilian equity security universe

## Objective

Define the deterministic **current security-level universe contract** for Brazilian-company equities on B3 using the evidence layers already audited after M20.

This block defines eligibility and produces an auditable current-universe artifact. It does **not** yet change the scoring engine, ranking API, weights, thresholds or historical backtests. Integration into the pre-scoring gate is a separate block.

## Eligibility chain

A company/security can enter the current Brazilian equity universe only when all applicable gates pass:

1. canonical issuer identity is `company_id = cvm:<CD_CVM>`;
2. the existing CVM jurisdiction contract classifies the issuer as `ELIGIBLE_BRAZILIAN_PUBLIC_COMPANY`;
3. current B3 `GetDetail` identity is coherent with the canonical B3 classification identity;
4. the security code is an exact code returned by that valid `GetDetail` identity;
5. the exact code has spot-market trading evidence in the current-year B3 COTAHIST;
6. all observed current-year `ESPECI` values for that exact code resolve coherently under the reviewed B3 taxonomy;
7. the coherent kind is one of:
   - `COMMON_SHARE`;
   - `PREFERRED_SHARE`;
   - `UNIT`.

No ticker number, company name, prefix/suffix convention or fuzzy matching participates in identity or eligibility.

## Company statuses

- `ELIGIBLE_CURRENT_BRAZILIAN_EQUITY`
- `EXCLUDED_ISSUER_NOT_ELIGIBLE`
- `EXCLUDED_DETAIL_UNAVAILABLE`
- `EXCLUDED_DETAIL_IDENTITY_CONFLICT`
- `EXCLUDED_SECURITY_CODE_IDENTITY_CONFLICT`
- `EXCLUDED_NO_CURRENT_CORE_EQUITY_SECURITY`

Issuer identity/code conflicts fail the whole company closed. A company may, however, have both a valid share and a non-core security such as a subscription bonus. In that case the valid share remains eligible while the non-core code remains explicitly excluded in security-level diagnostics.

## Security statuses

- `ELIGIBLE_CURRENT_CORE_EQUITY_SECURITY`
- `EXCLUDED_NO_CURRENT_SPOT_TRADE`
- `EXCLUDED_NON_CORE_SECURITY_KIND`
- `EXCLUDED_UNKNOWN_SECURITY_KIND`
- `EXCLUDED_SECURITY_TAXONOMY_CONFLICT`
- `EXCLUDED_SECURITY_CODE_IDENTITY_CONFLICT`

Unknown or conflicting `ESPECI` states never default to equity.

## Role of `dateQuotation`

B3 `dateQuotation` remains useful corroborative evidence for the listed-company surface, but it is **not** used to infer whether a code is ON, PN or Unit. Security type comes from observed B3 COTAHIST `ESPECI` semantics.

This separation is intentional: live validation found a foreign issuer (`PPLA`, `cvm:80152`) whose `PPLA11` trades as `UNT` while `dateQuotation` is absent. The jurisdiction contract correctly excludes the issuer before the security can enter the Brazilian-company universe.

## Current-time limitation

The contract combines current B3 `GetDetail` metadata with current-year COTAHIST trading evidence. It is a current operational universe, not a historical listing reconstruction.

`point_in_time_eligible = false`

Historical security membership must later be reconstructed from evidence valid at each historical date before being used in point-in-time backtests or walk-forward calibration.

## Live gate

The smoke artifact publishes:

- complete company decisions, including every excluded canonical identity;
- complete security decisions for eligible-jurisdiction issuers with valid B3 identity evidence;
- company and security status distributions;
- exact eligible company IDs and security codes;
- selected review cases including Petrobras, Brisanet, B100, BSCS, both Light identities, Porto Sudeste, Eurofarma and PPLA;
- latest observed COTAHIST date.

The live gate fails if the universe becomes unexpectedly small, if a reviewed positive/negative control changes unexpectedly, or if an unknown/conflicting B3 security taxonomy appears.

## Non-effects

This block does not yet:

- change `AnalyzerService.rank_current_brazilian_equities(...)`;
- filter scoring rows by security code;
- alter model routing or structural applicability reviews;
- modify score weights, thresholds or rankability semantics;
- claim historical/PIT security eligibility.

Those changes require separate gated blocks after this contract is empirically validated.
