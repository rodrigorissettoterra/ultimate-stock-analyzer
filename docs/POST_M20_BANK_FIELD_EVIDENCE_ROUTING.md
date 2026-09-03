# Post-M20 bank field evidence routing

## Purpose

This block introduces a diagnostic, field-level evidence router for the bank
fundamental contract. It does **not** change scoring, bootstrap persistence,
historical readiness, or walk-forward promotion.

The immediate problem is that `BankPrudentialAnnualRecord.point_in_time_eligible`
is record-level. That is too coarse once different official sources provide
stronger evidence for different fields.

## Evidence states

Each field in `bank_prudential_ifdata_v1` is classified into one of four states:

- `POINT_IN_TIME_ADMISSIBLE`: the selected observation is contract-scope
  compatible, available as of the simulated timestamp, and explicitly PIT
  eligible.
- `PRESENT_NOT_POINT_IN_TIME`: an official, contract-scope-compatible value is
  available, but revision/publication lineage is still insufficient for strict
  historical replay.
- `OFFICIAL_SCOPE_MISMATCH`: an official value exists with useful filing timing,
  but its consolidation perimeter is not proven equivalent to the prudential
  contract.
- `MISSING`: no usable observation is available as of the requested timestamp.

The router also preserves alternative official observations instead of silently
replacing one source with another.

## Source contracts

### BCB IFData

IFData remains the primary source for the current bank contract. Historical rows
are still treated as latest-state observations because the public API does not
provide a revision ledger, historical vintage selector, or row-level publication
timestamp. Existing values therefore remain `PRESENT_NOT_POINT_IN_TIME` unless a
future source contract explicitly upgrades them.

The contractual/estimated initial release date is used only as a lower bound. A
value is not even surfaced by the router before that timestamp.

### CVM DFP account 3.09

The previous audit validated account `3.09` (`Lucro/Prejuízo Consolidado do
Período`) for Itaú over the observed 2020-2025 DFP window with strict issuer
filing lineage.

That evidence is useful but has a different perimeter:

- CVM DFP `3.09`: issuer consolidated accounting scope;
- bank contract: prudential conglomerate scope.

Therefore `3.09` can be routed as an official alternative for
`annual_net_income`, but it remains `OFFICIAL_SCOPE_MISMATCH` until prudential
scope alignment and revision-history completeness are proven. It never silently
overwrites IFData.

If an IFData `annual_net_income` value is present, IFData remains selected and
CVM `3.09` is retained as an alternative observation.

### Pillar 3 / CVM IPE

The router accepts structured Pillar 3 prudential observations for:

- `core_equity_tier1_ratio`;
- `tier1_ratio`;
- `basel_ratio`;
- `leverage_ratio`.

Pillar 3 is scope-compatible and has stronger observed filing timestamps than
latest-state IFData. However, the currently proven IPE/Pillar 3 contract still
does not establish complete historical revision lineage. Those observations are
therefore routed as `PRESENT_NOT_POINT_IN_TIME`, never as strict PIT evidence.

## As-of behavior

All timestamps are required to be timezone-aware. The router filters evidence by
`as_of` and refuses to surface future IFData release estimates, future CVM
filings, or future Pillar 3 filings. This is a diagnostic anti-lookahead guard;
it does not by itself prove complete revision-aware replay.

## Coverage metrics

The report separates three notions that were previously collapsed:

1. `observed_critical_coverage`: any official selected observation exists,
   including scope-mismatched alternatives;
2. `contract_scope_compatible_critical_coverage`: selected evidence has the
   prudential contract perimeter;
3. `strict_point_in_time_critical_coverage`: selected evidence is both
   scope-compatible and PIT admissible.

`bank_evidence_point_in_time_ready` is true only when all critical bank fields are
strictly PIT admissible. `readiness_promotion_allowed` is hard-coded to `false`
in this block because this router is diagnostic only.

## Live smoke

The live smoke audits Itaú (`CD_CVM=19348`, CNPJ root `60872504`) for fiscal years
2024 and 2025. It downloads and hashes the official CVM DFP archives and the raw
BCB IFData payloads, routes the field evidence as of June 30 of the following
year, and asserts that:

- bank PIT readiness remains blocked;
- strict PIT critical coverage remains zero with the currently proven sources;
- CVM account `3.09` is visible either as the selected scope-mismatched
  alternative or as an alternative behind IFData;
- no routing decision promotes historical readiness.

## Non-goals

This block intentionally does not:

- modify `BankPrudentialAnnualRecord` persistence;
- change `FundamentalCoverageProfiler`;
- remove `BANK_EVIDENCE_NOT_POINT_IN_TIME`;
- claim issuer-consolidated and prudential-conglomerate equivalence;
- claim complete IPE/Pillar 3 revision history;
- run M15 backtests or M16 walk-forward calibration;
- change any score or weight.

The next implementation block can consume this routing contract in bootstrap and
coverage once each promoted field has a defensible source/perimeter/PIT contract.
