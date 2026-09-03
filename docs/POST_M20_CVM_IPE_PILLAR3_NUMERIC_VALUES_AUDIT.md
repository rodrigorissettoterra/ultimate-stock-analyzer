# Post-M20 CVM IPE Pillar 3 Numeric Values Audit

## Purpose

Validate deterministic extraction of the current-period prudential ratios from
versioned official CVM RAD Pillar 3 filings without changing overall bank
point-in-time readiness.

## Contract

For each observed filing, the parser uses the validated KM1 five-period row
layout (`T`, `T-1`, `T-2`, `T-3`, `T-4`) and selects the first percentage as
the filing's current-period value. The covered fields are:

- Capital Principal / CET1;
- Nível 1 / Tier 1;
- Índice de Basileia;
- Razão de Alavancagem (`RA (%)`).

Equivalent duplicate rows are accepted. Missing rows, non-five-period rows or
conflicting candidate rows fail closed.

## Version semantics

Every extracted observation keeps the CVM delivery protocol, version, PDF hash
and conservative `available_from`. An as-of lookup selects only observations
whose `available_from` is not after the requested instant, so an observed
re-presentation replaces version 1 only from its own availability date forward.

This proves deterministic replay over the **observed filing ledger**. It does
not prove that the CVM IPE archive exposes every historical correction that may
have existed.

## Readiness boundary

A successful live audit resolves only the numeric extraction sub-contract.
`BANK_EVIDENCE_NOT_POINT_IN_TIME` and
`PILLAR3_IPE_REVISION_HISTORY_COMPLETENESS_UNPROVEN` remain active. No bank
scoring or historical backtest readiness is promoted by this block.
