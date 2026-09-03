# Post-M20 CVM Bank Net-Income Canonical Mapping Audit

## Purpose

The preceding live diagnostic established that Itaú's consolidated CVM DFP DRE does not use generic account `3.11` for consolidated net income in fiscal years 2024 and 2025. Both filings instead expose `3.09` as `Lucro/Prejuízo Consolidado do Período`.

This block tests whether `3.09` is stable enough to support an issuer-scoped canonical mapping over a broader historical window before the bank source router is revisited.

## Validation window

The live smoke audits CVM code `19348` for fiscal years 2020 through 2025. Each official annual DFP archive is hashed and parsed through the existing CVM ingestion path.

Unlike a latest-only point-in-time selection, this audit keeps every filing version currently observed in the official annual archive and validates each version separately.

## Canonical mapping checks

For every observed issuer/year/version tuple, the audit requires:

- one unambiguous DRE account `3.09`;
- normalized label exactly equivalent to `Lucro/Prejuízo Consolidado do Período`;
- DRE accounts `3.07` and `3.08` such that `3.09 = 3.07 + 3.08`, within a BRL 1,000 rounding tolerance;
- a non-null filing availability timestamp attached to `3.09`;
- no duplicate account codes inside the audited consolidated DRE version.

When `3.09.01` and `3.09.02` are both present, the audit also records whether their sum corroborates `3.09`. This attribution identity is supporting evidence rather than a hard prerequisite because the canonical target is consolidated period income, not only income attributable to the parent shareholders.

## What a pass means

If every requested year is present and every observed filing version satisfies the checks above, the audit may set:

- `canonical_mapping_supported_for_observed_scope = true`;
- `canonical_account_code = 3.09`.

That conclusion is deliberately limited to the audited issuer, years, filing layout and versions observed in the current official DFP archives. It is not yet a universal bank-sector mapping.

## What remains blocked

Even after a successful mapping validation, two independent boundaries remain fail-closed:

- `CVM_BANK_DFP_REVISION_HISTORY_COMPLETENESS_UNPROVEN`: observing versions present in the current annual archive does not prove that the archive exposes every historical revision needed for arbitrary as-of replay;
- `CVM_BANK_DFP_PRUDENTIAL_SCOPE_ALIGNMENT_UNPROVEN`: CVM issuer consolidated accounting scope has not yet been proven equivalent to the BCB prudential conglomerate perimeter used by bank-specific metrics.

Accordingly, this block never sets overall bank point-in-time readiness or ranking readiness to true.

## Follow-up

After this mapping is validated, the bank source-routing audit can be rebuilt from current `main` using `3.09` for the supported Itaú scope. Other candidate DRE inputs observed in the same bank layout, including expected credit loss (`3.02.02`) and service/fee income (`3.01.05`), require their own semantic and formula audits before production routing.
