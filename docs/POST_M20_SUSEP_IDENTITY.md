# Post-M20 — SUSEP issuer/entity identity contract

## Purpose

Listed-company scoring must never connect a CVM/B3 issuer to SUSEP data by ticker, company name, substring, or fuzzy similarity. SUSEP's public licensed-entities registry exposes supervised-entity identity data including CNPJ and Código FIP, which provides the deterministic bridge required by the project.

## Contract

The implementation normalizes the issuer CNPJ to exactly 14 digits and matches only records whose official registry CNPJ is identical. Código FIP is treated as a digit string and leading zeroes are preserved.

A match returns every distinct `(CNPJ, Código FIP)` pair. This is deliberate: the broader insurer model must not assume that a listed insurance group is always represented by a single supervised legal entity. Any future aggregation across several supervised entities must be supported by separately verified ownership/group evidence and must aggregate financial numerators and denominators before ratios are calculated.

Names remain evidence/display metadata only. They are never identity keys.

## Fail-closed rules

- malformed CNPJ -> error;
- malformed Código FIP -> error;
- no exact CNPJ match -> no supervised entity returned;
- similar legal/trade name -> ignored unless CNPJ matches exactly;
- duplicate registry rows for the same CNPJ/FIP pair -> de-duplicated deterministically;
- no ticker-based or fuzzy fallback.

## Source boundary

`SusepLicensedEntityRecord` represents evidence already obtained from SUSEP's official licensed-entities registry. This module does not yet claim to be a live parser for the registry form. A live collector may be added only after its request/response contract is independently verified against the official source.

This identity contract does not alter the point-in-time status of SES financial data. Current SUSEP historical downloads remain revision-prone and `point_in_time_eligible=false` for strict historical backtests.
