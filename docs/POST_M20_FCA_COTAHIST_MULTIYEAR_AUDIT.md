# Post-M20 — Multiyear FCA × B3 COTAHIST security audit

## Objective

Validate the current Brazilian listed-equity security universe with two official sources
before defining a deterministic security-level inclusion rule.

This block is diagnostic only. It does not change scoring, ranking, rankability,
backtesting or the pre-scoring universe gate.

## Why the current-year FCA snapshot is insufficient

The CVM describes the Formulário Cadastral (FCA) as a periodic and eventual filing.
Its open-data dataset exposes structured filings delivered over a rolling five-year
window. Therefore, absence from the current-year ZIP does not prove that a currently
traded security does not exist.

The previous current-year-only experiment correctly exposed this limitation and was
closed without merge.

## Cross-source contract

The audit uses:

1. the current B3 industry-classification snapshot to define the candidate canonical
   issuer set;
2. CVM FCA files for the current year and four prior years to establish exact historical
   `ticker -> company_id` mappings and preserve FCA security metadata;
3. B3 COTAHIST for the current year as direct evidence that an exact FCA ticker actually
   traded in the spot market.

Canonical identity remains:

`company_id = cvm:<CD_CVM>`

No ticker prefix, suffix convention, issuer name, fuzzy match or heuristic identity rule
is permitted.

## Identity conflicts

If one exact ticker maps to more than one canonical CVM issuer in the five-year FCA
window, the ticker is reported as an identity conflict and its B3 trading evidence is
not assigned to either issuer.

The audit fails closed on identity, not on market activity.

## B3 specification

The COTAHIST parser now preserves the official `ESPECI` field as `specification`.
Examples in the B3 layout include `ON`, `ON ED`, `PN`, `PNA` and related values.

This block records the raw B3 specification. It does not yet convert those values into
a final project eligibility taxonomy.

## Review set

The generated artifact highlights the 24 domestic issuers that the abandoned
current-year-only rule would have excluded, including Light, Brisanet, Raízen, C&A,
Priner and BSCS.

For every reviewed issuer the artifact records:

- exact FCA tickers found across five years;
- whether a 2026 FCA row exists;
- exact tickers observed trading in B3 COTAHIST 2026;
- latest observed trade date;
- raw B3 `ESPECI`;
- latest FCA security metadata.

It also emits every candidate issuer that still lacks exact current-year B3 trading
evidence after the multiyear reconciliation.

## Point-in-time limitation

This is a current-state reconciliation. It is explicitly
`point_in_time_eligible = false`.

Historical backtests must continue to use revision-aware point-in-time contracts rather
than backfilling this current snapshot.

## Sources

- CVM FCA open data:
  `https://dados.cvm.gov.br/dataset/cia_aberta-doc-fca`
- B3 historical quotations:
  `https://www.b3.com.br/pt_br/market-data-e-indices/servicos-de-dados/market-data/historico/mercado-a-vista/cotacoes-historicas/`
- B3 COTAHIST layout:
  `https://www.b3.com.br/data/files/33/67/B9/50/D84057102C784E47AC094EA8/SeriesHistoricas_Layout.pdf`
