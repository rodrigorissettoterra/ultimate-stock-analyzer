# Post-M20 — FIGE CVM financial-statement tree audit

## Objective

Expose the actual CVM DFP account hierarchy used by FIGE / Investimentos Bemge (`cvm:6041`) before defining a non-prudential financial accounting contract.

Earlier post-M20 audits established two facts:

1. FIGE's numeric CVM account codes do not carry the same semantics as the `general_corporate` fixed-account mapping;
2. FIGE's canonical issuer CNPJ does not resolve to a BCB IFData prudential-conglomerate leader, so the existing bank contract cannot be activated through the project's exact identity rules.

The safe next step is therefore to inventory FIGE's own official CVM account tree rather than infer a profile from a different issuer type.

This block is **diagnostic only**. It does not change account mappings, model routing, scoring, weights, rankability, valuation, API output or backtesting.

## Evidence scope

The live smoke loads official CVM DFP 2025 individual-company:

- `BPA`;
- `BPP`;
- `DRE`.

Identity is fixed to `company_id = cvm:6041`. Ticker and issuer-name matching are not used.

For the latest reference date, only `ORDEM_EXERC = ÚLTIMO` is retained. Duplicate exact statement/account-code rows use the highest filing version and then `document_id`.

## Bounded account tree

The artifact exposes account codes through four hierarchy levels. Each retained row contains:

- statement;
- exact account code;
- official account name;
- reported BRL value;
- account depth;
- consolidation/document context;
- filing version/document ID.

The depth bound exposes the statement template and economically meaningful parent/sub-parent accounts while avoiding persistence of the full annual CVM archive.

## Important non-inference rule

This audit does **not** map account names to project metrics.

For example, discovering an official row called `Patrimônio Líquido` is evidence about where that concept appears in FIGE's filing, but the code is not promoted into production until its stability and applicability are validated across the required periods.

Likewise, zero reported values remain genuine reported zero values only when a row exists. An absent row remains missing/UNKNOWN.

## Acceptance path

After reviewing the live tree:

1. identify exact candidate FIGE codes for core financial concepts from official labels;
2. audit those candidates across multiple annual periods to verify code/label stability and revision behavior;
3. define a dedicated non-prudential financial statement contract only for stable, validated concepts;
4. design a FIGE-appropriate economic scoring model separately from the accounting mapping;
5. change routing only after both contracts are validated.

## Temporal boundary

The current CVM archive is latest-state evidence and is not treated as complete revision-history PIT data. The artifact therefore remains:

- `effect = diagnostic_only`;
- `point_in_time_eligible = false`.
