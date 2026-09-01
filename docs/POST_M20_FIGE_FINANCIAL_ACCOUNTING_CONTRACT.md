# Post-M20 — FIGE CVM financial accounting contract v1

## Objective

Formalize the first exact-account accounting contract for FIGE / Investimentos Bemge (`cvm:6041`) using only concepts whose CVM DFP codes and official labels were proven stable across 2021–2025.

This block defines an **accounting contract only**. It does not activate a sector model, change routing, calculate a new score, alter rankability, modify valuation, change API output or make the contract point-in-time eligible for strict backtesting.

## Evidence basis

The contract follows three completed diagnostics:

1. the existing `general_corporate` numeric mappings were shown to carry incorrect semantics for FIGE;
2. FIGE's canonical CNPJ did not resolve to a BCB IFData prudential identity, excluding reuse of the current bank contract;
3. 16 candidate CVM statement/account-code bindings kept the same exact official labels in every DFP from 2021 through 2025.

The contract therefore uses only those validated exact bindings.

## Identity boundary

Applicability is currently restricted to:

`company_id = cvm:6041`

No ticker, issuer name, group affiliation or fuzzy matching is used.

The issuer-bounded CVM loader filters both statement rows and filing metadata to exact `CD_CVM = 6041` before normalization. Ambiguity inside FIGE still fails closed; unrelated issuer metadata cannot contaminate this contract audit.

## Critical inputs

The v1 critical set is:

- `total_assets` — `BPA 1`;
- `cash_and_equivalents` — `BPA 1.01`;
- `financial_assets` — `BPA 1.02`;
- `equity` — `BPP 2.07`;
- `financial_intermediation_revenue` — `DRE 3.01`;
- `financial_intermediation_expense` — `DRE 3.02`;
- `gross_financial_intermediation_result` — `DRE 3.03`;
- `pretax_income` — `DRE 3.05`;
- `income_tax` — `DRE 3.06`;
- `net_income` — `DRE 3.11`.

## Supporting inputs

The supporting set is:

- `securities_amortized_cost` — `BPA 1.02.04.03`;
- `financial_liabilities_amortized_cost` — `BPP 2.02`;
- `provisions` — `BPP 2.03`;
- `fiscal_liabilities` — `BPP 2.04`;
- `other_operating_result` — `DRE 3.04`;
- `continuing_operations_income` — `DRE 3.07`.

## Semantic guard

Each binding stores both the exact code and its expected official CVM label.

Extraction requires:

`statement + account_code + expected_label`

Whitespace is normalized only. Case, accents and wording remain significant. If a numeric code appears with a different label, extraction fails closed instead of assuming semantic equivalence.

If a binding is absent, the concept stays missing/UNKNOWN. If the official row exists with value zero, zero remains a known reported value.

## Live acceptance gate

The live smoke evaluates the contract independently for each year from 2021 through 2025 and requires:

- critical coverage = `1.0`;
- total coverage = `1.0`.

The artifact preserves the exact extracted values and coverage result for every year. If any year becomes incomplete, the artifact is written and the workflow fails.

## Non-effects

The contract evaluation reports:

- `effect = contract_defined_not_routed`;
- `point_in_time_eligible = false`.

No downstream scoring component is allowed to treat this contract as active until a separate economic-model applicability block is completed.

## Next decision

After this accounting contract passes live validation, the next block must determine what economic metrics are appropriate for FIGE's business model. That work should distinguish accounting availability from model suitability and should not reuse the bank score merely because the statement layout resembles a financial institution.
