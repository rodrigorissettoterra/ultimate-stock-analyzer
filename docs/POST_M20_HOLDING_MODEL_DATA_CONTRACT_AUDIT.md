# Post-M20 — Holding-model data-contract audit

## Objective

Determine whether the three remaining structural applicability reviews — FIGE (`cvm:6041`), B100 (`cvm:27634`) and ITSA (`cvm:7617`) — can support a specialized holding/investment-company model from official free CVM statement data.

This block is **diagnostic only**. It does not change sector routing, score formulas, weights, rankability, valuation, API results or backtests.

## Why this audit is needed

The current `general_corporate` model emphasizes operating-company metrics such as ROIC, EBIT margin, free-cash-flow margin and net debt/EBITDA. Those measures can be structurally misleading for companies whose economic result is dominated by investments in subsidiaries/associates and equity-method income.

The active applicability registry v0.2 therefore keeps FIGE, B100 and ITSA under explicit model review after universe eligibility has already been resolved.

## Evidence scope

The smoke uses official CVM DFP 2025 **individual-company** statements (`BPA`, `BPP`, `DRE`) for the canonical identities:

- `cvm:6041` — FIGE;
- `cvm:27634` — B100;
- `cvm:7617` — ITSA.

DFP 2025 is used because it is the latest completed annual fiscal period shared by the three cases at the time of this audit.

## Candidate-account discovery

The audit intentionally does **not** hard-code a new holding account contract before observing the real CVM rows.

It exposes candidate rows whose official account descriptions indicate:

- investments / participações societárias / investments in controlled or associated companies;
- resultado de equivalência patrimonial.

These description matches are diagnostic discovery only. They do not establish issuer identity and do not become scoring inputs merely because they matched a term.

Canonical issuer identity remains `company_id = cvm:<CD_CVM>` throughout.

## Unambiguous baseline accounts

For context, the audit also reads existing exact top-level CVM mappings where available:

- total assets (`BPA 1`);
- cash (`BPA 1.01.01`);
- current financial investments (`BPA 1.01.02`);
- current/noncurrent borrowings (`BPP 2.01.04`, `2.02.01`);
- equity (`BPP 2.03`);
- parent net income (`DRE 3.11.01`, with `3.11` fallback).

When exactly one investment/equity-method candidate exists, the diagnostic may expose:

- candidate investments / total assets;
- candidate equity-method result / parent net income.

When multiple candidate rows exist, the aggregate is deliberately `UNKNOWN` (`None`) to prevent parent/child account double counting. Every matching row remains visible in the artifact for review.

## Fail-closed behavior

The live smoke fails if any of the three canonical companies has no DFP statement evidence at all.

Within a company, missing or ambiguous holding-specific accounts remain `UNKNOWN`, accompanied by explicit warnings such as:

- `NO_INVESTMENT_ACCOUNT_CANDIDATE`;
- `NO_EQUITY_METHOD_ACCOUNT_CANDIDATE`;
- `MULTIPLE_INVESTMENT_ACCOUNT_CANDIDATES`;
- `MULTIPLE_EQUITY_METHOD_ACCOUNT_CANDIDATES`.

No missing value is converted to zero.

## Acceptance path after the artifact

A specialized holding model should only be proposed after the live artifact establishes coherent account semantics and availability. Candidate future dimensions include:

1. investment assets relative to total assets;
2. equity-method contribution to earnings;
3. holding-level cash and debt relative to equity or portfolio value;
4. dividend/upstream cash generation;
5. portfolio concentration/diversification;
6. NAV/SOTP discount where contemporaneous ownership stakes and market values can be reconstructed reliably.

ITSA may support a richer NAV/SOTP model because its portfolio is publicly disclosed. B100 may require transitional/reorganization treatment. FIGE needs empirical account-level confirmation before either classification is assumed.

## Point-in-time limitation

The diagnostic is based on the currently downloaded CVM DFP archive and is marked `point_in_time_eligible = false` for strict historical backtests. A future PIT holding model must use document availability timestamps and, for NAV components, contemporaneous ownership stakes and security prices.
