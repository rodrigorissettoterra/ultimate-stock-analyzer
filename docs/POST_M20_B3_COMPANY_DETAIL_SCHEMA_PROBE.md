# Post-M20 — B3 listed-company GetDetail schema probe

## Objective

Discover the exact public JSON schema returned by the current B3 Listed Companies
`GetDetail` endpoint before using it as a source for the current security universe.

This is a diagnostic-only block. It does not alter scoring, ranking, rankability,
backtesting, issuer eligibility or the pre-scoring universe gate.

## Why this probe exists

The current-year FCA experiment proved that a filing-year snapshot is not a complete
current security master. A subsequent rolling-FCA audit could not be live-validated
because the official CVM data host became unreachable from GitHub-hosted runners.

The B3 Listed Companies site independently exposes current company details by exact
CVM code, including public surfaces for trading codes, ISIN, CNPJ and listing data.
Before implementing a typed collector, this block observes the live JSON shape rather
than guessing field names from rendered pages or third-party scrapers.

## Controls

The live probe queries five exact CVM codes already established by official identity
sources:

- `9512` — Petrobras, positive control;
- `27693` — Brisanet, a suspicious false exclusion in the abandoned FCA-2026 rule;
- `27634` — B100, known listed-equity case;
- `8036` — Light, absent from the FCA-2026 security snapshot;
- `18759` — Brazilian Securities Companhia de Securitização, the BSCS review case.

## Artifact policy

The workflow does **not** persist the complete raw API response. The artifact contains:

- top-level field names;
- nested schema paths and value types;
- public scalar values only for paths whose names relate to company/security identity,
  ticker/code, ISIN, CNPJ, market, quotation, listing, shares or BDR metadata.

Long scalar strings are bounded.

## Safety

- requests are keyed by exact `codeCVM`;
- no ticker prefix/suffix rule is used;
- no company-name or fuzzy matching is used;
- no response field is interpreted as an eligibility decision in this block;
- current-state observations remain `point_in_time_eligible = false`.

The next implementation step may define a typed B3 company-detail collector only after
the live artifact confirms the field names and shapes.
