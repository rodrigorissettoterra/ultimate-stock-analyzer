# Post-M20 — Current FCA security-universe audit

## Objective

Observe the exact current CVM FCA security-master fields needed for a future deterministic Brazilian-equity security eligibility contract **before** defining that contract.

This block is diagnostic only. It does not include or exclude a security from ranking.

## Why this gate is necessary

Issuer jurisdiction and security eligibility are different questions.

The current CVM jurisdiction contract can establish that a canonical issuer is a Brazilian public company, but a B3 classification row does not by itself prove that the issuer has a currently listed share eligible for the project's equity ranking. A securitization issuer, for example, may appear in B3 economic classifications because it issues listed securities without having a listed common/preferred share in the intended equity universe.

## Source and identity

The audit uses the official structured CVM Formulário Cadastral (FCA) security table for the current year.

Identity remains:

`company_id = cvm:<CD_CVM>`

Ticker, ISIN, `security_type`, `market` and administrator are security attributes, not issuer-identity inference keys.

## Audit behavior

For every canonical `company_id + ticker`, the audit selects the latest observed FCA row by:

1. reference date;
2. document version;
3. official availability timestamp when present.

It then reports distributions for currently active latest rows and exact selected-company rows for the post-M20 review cases.

The initial live controls are:

- `cvm:6041` / FIGE;
- `cvm:18759` / BSCS;
- `cvm:27634` / B100;
- `cvm:7617` / ITSA;
- `cvm:9512` / Petrobras as a positive FCA security-master control.

## Non-effects

This gate does not yet define which exact `security_type` values qualify as Brazilian equity. It does not alter scoring, rankability, weights, universe decisions or backtests.

Only after the live FCA distributions and selected cases are reviewed may a later block define a deterministic security-level eligibility rule.

## Point-in-time limitation

The artifact is a current-state audit. It is explicitly `point_in_time_eligible = false` and must not be used to reconstruct a historical security universe.
