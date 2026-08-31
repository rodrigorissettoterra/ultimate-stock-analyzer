# Post-M20 — B3 current-security audit

## Objective

Establish auditable current security evidence for the B3 candidate universe before defining a final instrument-level eligibility rule.

This block is diagnostic only. It does not change scoring, ranking, rankability, backtests or the current issuer-jurisdiction gate.

## Why B3 GetDetail is used

The current-year FCA file is a periodic/event-driven filing snapshot and proved unsuitable as a complete current security master. B3's official Listed Companies `GetDetail` surface exposes current company identity and security-code fields keyed by exact `codeCVM`.

The audit therefore uses three official B3 surfaces:

1. current industry classification + active company catalog for canonical `company_id = cvm:<CD_CVM>`, CNPJ and issuer code;
2. `GetDetail` by exact `codeCVM` for `code`, `otherCodes[].code/isin` and `dateQuotation`;
3. current-year COTAHIST for direct exact-code trading evidence and raw `ESPECI`.

## Identity contract

No ticker suffix, prefix, issuer name or fuzzy match creates identity.

`GetDetail` is accepted only when its canonical CVM code matches the requested company and its returned issuer code/CNPJ do not conflict with the already audited B3 classification identity.

If one exact returned security code belongs to multiple canonical companies, trading evidence for that code is not assigned to either company.

## Important semantic boundary

B3 presents `dateQuotation` as the beginning of share trading. That field is therefore useful share-level evidence.

However, `otherCodes` is not itself an equity-only list. Live probing showed that a company detail can mix equity and debt codes. Consequently this audit records exact codes and COTAHIST `ESPECI`, but does not yet define the final accepted `ESPECI` taxonomy.

## Diagnostic states

- `DETAIL_UNAVAILABLE`
- `DETAIL_IDENTITY_CONFLICT`
- `SECURITY_CODE_IDENTITY_CONFLICT`
- `NO_B3_SHARE_QUOTATION_DATE`
- `B3_SHARE_DATE_WITH_CURRENT_SPOT_TRADE`
- `B3_SHARE_DATE_WITHOUT_CURRENT_SPOT_TRADE`

These are evidence states, not investment recommendations.

## Current-state limitation

The artifact is explicitly `point_in_time_eligible = false`. Current GetDetail/COTAHIST evidence must not be backfilled into historical walk-forward universes.

## Next gate

After inspecting the live distribution of `ESPECI` among companies with B3 share-quotation evidence, a later block may define the deterministic current instrument taxonomy and integrate it before scoring.
