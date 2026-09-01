# Post-M20 — FIGE BCB IFData applicability audit

## Objective

Determine whether FIGE / Investimentos Bemge (`company_id = cvm:6041`) can legitimately reuse the existing BCB IFData prudential-bank data contract.

This follows the CVM account-schema audit, which proved that FIGE does not use the same financial-statement semantics as the `general_corporate` fixed-account mapping. The next safe question is therefore not whether FIGE merely looks financial, but whether its canonical issuer identity resolves to the exact prudential identity contract already used by the bank model.

This block is **diagnostic only**. It does not change sector routing, account mappings, scoring, weights, rankability, valuation, API output or backtesting.

## Identity contract

The audit uses two official sources:

1. CVM issuer registry to retrieve the canonical `cvm:6041` issuer and its official CNPJ;
2. BCB IFData `Cadastro` for the audited annual period.

The existing project function `resolve_prudential_identity(...)` is reused unchanged. A match requires:

- exact CNPJ root of the CVM issuer;
- active IFData row;
- the same root in `CnpjInstituicaoLider`;
- a prudential-conglomerate code;
- `CodInst == CodConglomeradoPrudencial`.

Ticker, issuer name, B3 sector label and fuzzy matching are not used.

## Diagnostic statuses

### `EXACT_PRUDENTIAL_IDENTITY_FOUND`

The canonical CVM issuer CNPJ resolves exactly to a BCB prudential-conglomerate leader under the existing IFData identity contract.

Only after this status is established does the live script collect the annual bank profile and evaluate the existing `BANK_PRUDENTIAL_CONTRACT` coverage.

### `NO_PRUDENTIAL_IDENTITY`

No exact active prudential-conglomerate leader exists for the canonical CVM issuer CNPJ root in the audited IFData period.

This is a valid diagnostic result. It must **not** be replaced with a name-based, ticker-based, group-company or parent-company inference.

If this is the live result for FIGE, the existing bank model cannot be activated from the current IFData identity contract. A separate CVM financial-statement profile must then be designed and validated.

## Bank-profile coverage

When an exact prudential identity exists, the audit additionally reports:

- whether one annual `BankPrudentialAnnualRecord` was produced;
- critical and total coverage of `BANK_PRUDENTIAL_CONTRACT`;
- missing critical/supporting fields;
- bounded bank metrics including assets, equity, credit portfolio, net income, credit losses, Basel/Tier 1/CET1/leverage, ROE, ROA, cost of credit, equity/assets, efficiency and fee-income share.

No absent metric becomes zero.

## Acceptance path

The live artifact determines the next branch:

1. **Exact prudential identity + adequate profile:** evaluate whether FIGE's economic business model is sufficiently bank-like to reuse the bank scoring model; identity alone is not enough to change routing.
2. **No prudential identity:** define a dedicated non-prudential financial accounting contract from official CVM statement semantics before any FIGE scoring/routing change.
3. **Exact identity but poor bank-contract coverage:** keep FIGE fail-closed for specialized scoring and diagnose which prudential evidence is missing.

## Temporal boundary

IFData historical rows are collected from the API's latest state and do not expose a complete revision history. Therefore this audit remains:

- `effect = diagnostic_only`;
- `point_in_time_eligible = false`.

It must not be interpreted as historical PIT eligibility for backtests.
