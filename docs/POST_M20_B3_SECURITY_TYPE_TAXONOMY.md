# Post-M20 — B3 ESPECI security-type taxonomy

## Objective

Translate raw B3 COTAHIST `ESPECI` values into an explicit, fail-closed current security-type taxonomy before any instrument-level universe rule is activated.

This block is diagnostic only. It does not change scoring, ranking, rankability, issuer eligibility, the current pre-scoring gate or historical/backtest behavior.

## Official semantics

The B3 COTAHIST layout defines `ESPECI` as the security specification and documents, among others:

- `ON` as ordinary/common shares;
- `PN`, `PNA`, `PNB`, `PNC`, `PND`, `PNE` as preferred-share classes;
- `BNS` as subscription bonuses;
- `DIR` as subscription rights;
- `ON REC`, `PN REC` and related forms as subscription receipts rather than the underlying shares.

B3 separately defines Units as certificates composed of more than one security class, commonly ordinary and preferred shares. Current COTAHIST represents them with base `UNT`.

B3 BDR material uses `DR1`, `DR2`, `DR3`, `DRE` and `DRN` classes.

Porto Sudeste V.M. explicitly states that `PSVM11`, B3 specification `TPR`, is a variable-remuneration title based on royalties and that the company does not have shares in trading. `TPR` therefore cannot be treated as an equity security merely because it trades in the cash market.

## Current taxonomy

Core equity security kinds:

- `COMMON_SHARE`
- `PREFERRED_SHARE`
- `UNIT`

Explicit non-core or unsupported kinds:

- `SUBSCRIPTION_RECEIPT`
- `SUBSCRIPTION_BONUS`
- `SUBSCRIPTION_RIGHT`
- `BDR`
- `VARIABLE_ROYALTY_TITLE`
- `SHARE_DEPOSIT_CERTIFICATE`
- `FUND`
- `OTHER_UNKNOWN`

Event and governance suffixes such as `ED`, `EJ`, `ATZ`, `NM`, `N1` and `N2` do not change the underlying share class. However, `REC` is semantically material and is classified as a subscription receipt before the base share class is considered.

## Fail-closed behavior

An unreviewed base token is `OTHER_UNKNOWN`, never a share by default.

If the same exact security code exhibits raw specifications that resolve to more than one security kind during the audit window, the code is flagged as a taxonomy conflict and is not considered core equity by the diagnostic profile.

No ticker number, suffix convention, company name or fuzzy rule participates in the taxonomy.

## Live validation

The existing B3 current-security smoke now reports:

- current exact security codes with COTAHIST evidence;
- counts by coherent security kind;
- number of core-equity security codes;
- number of companies with at least one current core-equity trade;
- taxonomy conflicts;
- unknown/unreviewed security samples.

The next block may turn this reviewed taxonomy into a deterministic current instrument-eligibility contract, but only after the live artifact shows zero unexpected kind conflicts/unknowns in the intended equity population.

## Sources

- B3 COTAHIST layout: `https://www.b3.com.br/data/files/33/67/B9/50/D84057102C784E47AC094EA8/SeriesHistoricas_Layout.pdf`
- B3 Units: `https://www.b3.com.br/pt_br/produtos-e-servicos/negociacao/renda-variavel/certificado-de-deposito-de-acoes-units.htm`
- Porto Sudeste investor portal: `https://www.portosudeste.com/investidores/`
