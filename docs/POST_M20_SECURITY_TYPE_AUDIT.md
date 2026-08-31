# Post-M20 — CVM/FCA security-type audit

## Objective

Observe the exact official FCA/CVM security fields needed to define the Brazilian-equity universe without inferring instrument type from ticker shape, company name, or issuer code.

This gate is diagnostic only and does not alter universe eligibility, scoring, rankability, weights, or thresholds.

## Audit controls

The bounded live smoke requests the latest completed FCA year for:

- `PETR4` — ordinary control for a Brazilian listed equity security;
- `G2DI33` — canonical issuer `cvm:80195`, currently under universe eligibility review;
- `PPLA11` — canonical issuer `cvm:80152`, currently under universe eligibility review.

The audit records the normalized FCA values for:

- `company_id`;
- ticker;
- ISIN;
- `security_type`;
- market;
- administrator;
- reference date;
- document version;
- availability timestamp when evidenced;
- source document.

## Selection rule

Ticker is used only to select security records. The issuer identity continues to be `company_id = cvm:<CD_CVM>`.

When multiple FCA observations exist for a ticker in the downloaded archive, the audit selects the latest reference date, then the highest document version, then the latest evidenced availability timestamp.

## Acceptance behavior

`PETR4` must resolve in the normalized FCA security master; otherwise the smoke fails because the live schema/identity contract is not trustworthy enough for the audit.

The two review cases remain non-blocking if absent. Their absence is reported explicitly rather than converted into an eligibility decision.

## Next gate

Only after the live artifact shows the exact observed FCA security-type values may a later block define a deterministic security eligibility classifier. That classifier must remain separate from issuer identity and must not infer BDR/equity status from ticker suffix alone.
