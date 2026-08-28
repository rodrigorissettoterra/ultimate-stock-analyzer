# M11 — Securities Lending

Status: **implemented in v1.1 candidate**.

## Principle

Securities lending has two different meanings for an investor and they must not be collapsed:

1. **RentalOpportunityScore** — potential attractiveness of lending income for a holder/donor.
2. **ShortPressureRisk** — intensity of borrowing demand that may be associated with short exposure.

A high lending fee can therefore be positive for income and simultaneously a risk signal.

## Official free source

B3 is the source of truth. In 2026 the former public-data pages were retired and the content was
migrated to the Boletim Diário do Mercado (BDI). The engine models the two official datasets:

- **LoanBalanceFile / Empréstimos registrados** — daily flow: number of contracts, quantity,
  financial value and donor/taker min/average/max annual lending rates;
- **LendingOpenPositionFile / Posições em aberto** — end-of-day stock: open quantity, average
  trade price, price factor and balance value.

Daily flow (`QtyShrDay`) is never used as a substitute for open stock (`BalQty`).

## Metrics

When source coverage allows, M11 calculates:

- donor average annual rate;
- taker average annual rate;
- open loan quantity and value;
- `LoanUtilization = open_quantity / free_float_shares`;
- utilization change over 20 open-position observations;
- daily contracts, loaned quantity and value;
- daily flow / free float;
- opportunity and short-pressure component scores;
- coverage and confidence;
- provisional `NetLendingScore`, which keeps the two source scores visible.

If free float or open positions are missing, utilization is `UNKNOWN`; it is never estimated from
daily lending flow. Missing data reduces coverage and may make the result non-rankable.

## Rate semantics

Internal rates use decimals (`0.05 = 5% p.a.`). B3 percentage-point fields such as `5,00%` are
normalized at ingestion. Cross-market daily averages derived by this project are weighted by
loaned quantity and are identified as aggregated values rather than presented as an original B3
published rate.

## Current BDI migration

B3 states that the former public-data pages were discontinued on 31 March 2026 after their
information had already been consolidated in BDI from 15 December 2025. The domain model and
parsers therefore depend on official field semantics rather than a legacy page URL.

## Public-repository safety

No bulk B3 dataset is committed to GitHub. Tests use synthetic rows with the official column tags.
The collector/runtime will reconstruct data from B3.

Weights and thresholds are hypotheses and remain subject to M15/M16 point-in-time backtesting and
walk-forward calibration.
