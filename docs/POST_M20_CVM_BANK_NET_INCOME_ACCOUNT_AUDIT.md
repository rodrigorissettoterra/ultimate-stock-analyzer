# Post-M20 CVM Bank Net-Income Account Audit

## Purpose

This diagnostic block isolates a bank-specific CVM DFP mapping risk discovered by the live source-routing smoke test.

The generic fixed-account extractor maps `net_income_consolidated` to DRE account `3.11`. The live Itaú DFP audit for fiscal 2024 did not observe that fixed account, so the bank source-routing PR was closed without merge rather than silently substituting a description match or treating the missing value as zero.

## Scope

The audit downloads the official CVM DFP archives for the requested years, records archive SHA-256 and size, loads consolidated DRE rows for the target CVM issuer, applies the existing point-in-time line selection, and emits:

- every observed current-fiscal-order consolidated DRE account;
- whether fixed account `3.11` is present;
- heuristic description-based candidates containing terms such as `lucro líquido`, `prejuízo`, `resultado líquido`, `resultado do período`, or `resultado atribuível`;
- filing availability timestamps, versions, source member names, values, and account codes.

The description heuristic is discovery evidence only. It is not a canonical account mapping.

## Fail-closed contract

The audit always preserves `CVM_BANK_NET_INCOME_ACCOUNT_UNPROVEN` and never promotes bank point-in-time readiness. When `3.11` is absent it also emits `CVM_BANK_FIXED_311_NOT_OBSERVED`.

A later block may promote a bank-specific net-income mapping only after the observed CVM account semantics are reviewed and shown to be stable enough for the supported issuer/year scope. Scope alignment between CVM issuer accounting statements and the BCB prudential conglomerate also remains a separate unresolved requirement.

## Live target

The smoke workflow audits CVM code `19348` for fiscal years 2024 and 2025. It intentionally requires only non-empty official DRE evidence and provenance, not a particular net-income account code.

This block is diagnostic only and makes no scoring, readiness, or production bank-evidence promotion.
