# Post-M20 Bank Point-in-Time Source Routing Audit

## Purpose

Separate the bank model's inputs by evidence status instead of treating one
annual IFData profile as an all-or-nothing point-in-time object.

## Proven observed PIT routes

The version-aware CVM IPE Pillar 3 ledger now provides observed filing timelines
for:

- Basel ratio;
- Tier 1 ratio;
- CET1 / Capital Principal;
- leverage ratio.

For the current ten-input bank prudential coverage contract, Basel and Tier 1
represent 20% of critical inputs. In the structural bank model they represent
16% of total model weight.

## Timestamped CVM candidates

CVM DFP consolidated filings expose publication timestamps and revision-aware
statement rows for total assets, equity and consolidated net income. Current and
prior fiscal years therefore provide timestamped candidates for:

- total assets and prior total assets;
- equity and prior equity;
- annual net income.

These candidates are **not promoted** to the bank prudential contract because the
CVM consolidated issuer perimeter has not yet been proven equivalent to the BCB
prudential-conglomerate perimeter used by the existing bank model. Counting
these candidates together with the validated Pillar 3 fields gives 70% of the
critical contract and 40.5% of structural model weight, but this is diagnostic
coverage only.

## Still unresolved for strict PIT

- gross credit portfolio and its prior-year value;
- annual credit-loss result;
- net interest margin;
- 90-day NPL ratio and NPL coverage;
- efficiency and fee-income fields currently sourced from latest-state IFData;
- loan growth derived from the unresolved credit portfolio.

Dividend metrics remain outside this bank-accounting PIT audit and retain their
own evidence lifecycle.

## Readiness boundary

The audit keeps the following blockers active:

- `BANK_EVIDENCE_NOT_POINT_IN_TIME`;
- `BANK_SCOPE_ALIGNMENT_UNPROVEN`;
- `BANK_GROSS_CREDIT_PIT_SOURCE_UNRESOLVED`;
- `BANK_CREDIT_LOSS_PIT_SOURCE_UNRESOLVED`;
- `BANK_MODEL_PIT_COVERAGE_INCOMPLETE`;
- `PILLAR3_IPE_REVISION_HISTORY_COMPLETENESS_UNPROVEN`.

No scoring or historical-backtest readiness is promoted by this block.
