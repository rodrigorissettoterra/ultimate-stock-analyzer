# Post-M20 — FIGE CVM statement-schema stability audit

## Objective

Verify whether the exact FIGE / Investimentos Bemge (`cvm:6041`) CVM DFP account codes identified in the validated 2025 statement-tree inventory preserve their official labels across 2021–2025.

This is the prerequisite for defining a dedicated non-prudential financial accounting contract.

The block is **diagnostic only**. It does not change production account mappings, sector/model routing, scores, weights, rankability, valuation, API output or backtesting.

## Why this audit exists

Previous evidence established that:

1. FIGE's numeric CVM account semantics are incompatible with the existing `general_corporate` fixed-account mapping;
2. FIGE's canonical CNPJ does not resolve to an exact BCB IFData prudential identity, so the bank contract cannot be reused;
3. the 2025 CVM tree exposes a coherent financial-institution-style statement template with its own account locations.

A production mapping must therefore be based on FIGE's own CVM schema and must not assume that one annual snapshot is stable historically.

## Candidate source

Candidate codes are copied explicitly from the previously validated official FIGE 2025 individual DFP tree. Examples include:

- `BPA 1` — `Ativo Total`;
- `BPA 1.02` — `Ativos Financeiros`;
- `BPA 1.02.04.03` — `Títulos e Valores Mobiliários`;
- `BPP 2.07` — `Patrimônio Líquido`;
- `DRE 3.01` — `Receitas de Intermediação Financeira`;
- `DRE 3.05` — `Resultado antes dos Tributos sobre o Lucro`;
- `DRE 3.06` — `Imposto de Renda e Contribuição Social sobre o Lucro`;
- `DRE 3.11` — `Lucro ou Prejuízo Líquido do Período`.

This list is a diagnostic candidate set, not yet a production metric contract.

## Issuer-bounded historical loading

The first multiyear smoke exposed a historical CVM metadata ambiguity for an unrelated issuer (`cvm:24600`) in the 2021 archive. The regular market-wide ingestion path correctly fails closed on that ambiguity, but the failure occurred before FIGE could be isolated.

For this issuer-specific diagnostic, each annual raw statement table and filing-metadata table is therefore filtered to exact `CD_CVM = 6041` **before** metadata attachment and normalization.

This does not relax validation for FIGE. If FIGE itself has ambiguous filing metadata, the targeted loader still fails closed. It only prevents unrelated issuers from contaminating an audit whose declared identity scope is one canonical company.

The normal production ingestion path is unchanged.

## Comparison rule

For each year from 2021 through 2025, the live smoke loads official CVM DFP individual `BPA`, `BPP` and `DRE`, builds the same bounded latest-revision statement tree, and then looks up each candidate by exact:

`statement + account_code`

No ticker, issuer-name, fuzzy account-name or economic-semantic matching is used.

Account labels are compared after whitespace normalization only. Case, accents and wording are otherwise preserved. Therefore a wording change on the same numeric code is surfaced as a review item rather than silently accepted as equivalent.

## Status contract

Each candidate receives one of the following diagnostic statuses:

- `STABLE_EXACT_LABEL` — exact code exists throughout the requested window and the official label matches the 2025 baseline;
- `LABEL_CHANGED_REVIEW` — exact code exists but at least one official label differs from the baseline;
- `MISSING_PERIOD` — exact code is absent in at least one requested year;
- `MISSING_AND_LABEL_CHANGED_REVIEW` — both conditions occur.

An absent code remains missing/UNKNOWN. A reported row with value zero remains a genuine reported zero.

## Core versus supporting candidates

The audit tags a bounded set of candidates as `core` because they are likely prerequisites for a future FIGE financial profile: total assets, cash, financial assets, equity, financial-intermediation revenue/expense/result, pretax income, taxes and net income.

Supporting candidates provide additional structural context such as securities at amortized cost, provisions and fiscal liabilities.

These tiers only organize diagnostic review. They do not activate scoring behavior.

## Acceptance path

After reviewing the live 2021–2025 artifact:

1. retain only concepts whose exact-code semantics are sufficiently stable;
2. explicitly document any schema breaks or unavailable periods;
3. define a dedicated FIGE/non-prudential financial accounting contract from the validated subset;
4. validate accounting coverage separately from economic-model suitability;
5. change routing only after both are proven.

## Temporal boundary

The CVM annual archives used here are current/latest-state copies of historical filings, not a complete revision-history snapshot system. Consequently this audit remains:

- `effect = diagnostic_only`;
- `point_in_time_eligible = false`.

Historical PIT eligibility must be established separately before strict backtesting uses the resulting profile.
