# Post-M20 — General-corporate CVM account-schema audit

## Objective

Determine whether the fixed CVM account codes used by the `general_corporate` model carry the same official accounting labels for the three remaining model-applicability cases: FIGE (`cvm:6041`), B100 (`cvm:27634`) and ITSA (`cvm:7617`).

This block is **diagnostic only**. It does not change account mappings, sector routing, score formulas, weights, rankability, API output, valuation or backtesting.

## Why this audit is needed

The holding-model data-contract audit showed that the same economic idea can appear under different CVM account-code families across these issuers. Before proposing a specialized model, the project must verify a more basic assumption: whether the existing `general_corporate` fixed-account contract itself has stable semantics for these companies.

The current fixed mapping includes concepts such as:

- `equity` -> `BPP 2.03`;
- `revenue` -> `DRE 3.01`;
- `gross_profit` -> `DRE 3.03`;
- `ebit` -> `DRE 3.05`;
- `pretax_income` -> `DRE 3.07`;
- `net_income_parent` -> `DRE 3.11.01`.

A numeric account code alone is not sufficient evidence that an issuer uses the same accounting concept as another issuer.

## Evidence scope

The live smoke uses official CVM DFP 2025 **individual-company** statements (`BPA`, `BPP`, `DRE`) for the canonical identities:

- `cvm:6041` — FIGE;
- `cvm:27634` — B100;
- `cvm:7617` — ITSA.

Only exact `company_id = cvm:<CD_CVM>` identity is used. Ticker, issuer name and fuzzy matching are never used to establish identity.

## Diagnostic contract

For every BPA/BPP/DRE account already present in `GENERAL_CORPORATE_FIXED_ACCOUNTS`, the audit records the latest available DFP row for each canonical company and preserves:

- internal fixed-account concept name;
- statement;
- exact CVM account code;
- official CVM account label;
- normalized label used only for exact textual comparison;
- value;
- reference date;
- document/consolidation context.

Each concept receives one of four diagnostic statuses:

### `CONSISTENT_ACCOUNT_LABEL`

All reviewed companies expose the exact code and the normalized official account label is identical across them.

### `DIVERGENT_ACCOUNT_LABEL`

All reviewed companies expose the exact code, but at least two different official labels are observed.

This status **does not automatically mean the concepts are economically incompatible**. It means the project cannot silently assume semantic equivalence from the account code alone.

### `PARTIAL_COVERAGE`

The exact account code exists for some reviewed companies but is absent for at least one.

### `MISSING_ALL`

The exact fixed-account code is absent for every reviewed company in the audited statements.

Missing evidence remains missing/`UNKNOWN`; it is never converted to zero.

## Revision handling

Within the latest reference date for each company, duplicate exact statement/account-code rows are resolved by the highest CVM filing `version`, then `document_id`, matching the project's existing revision-aware normalization conventions.

The audit does not claim that the current archive is sufficient for historical point-in-time reconstruction.

## Acceptance path after the artifact

The live artifact will determine the next branch:

1. if FIGE/B100/ITSA mostly share stable fixed-account semantics, the remaining problem is primarily economic-model applicability;
2. if material concepts such as revenue, EBIT, debt or equity show divergent labels or partial coverage, the project must establish a separate accounting mapping/profile before a specialized score is safe;
3. no scoring or routing change may be made from description similarity alone.

A specialized holding/financial-services model will only be implemented after both its economic formula and its authoritative account/data mappings are validated.

## Temporal boundary

The smoke uses the currently downloaded CVM DFP 2025 archive. The report is therefore marked:

- `effect = diagnostic_only`;
- `point_in_time_eligible = false`.

Historical backtests must continue to use explicitly revision-aware point-in-time evidence.
