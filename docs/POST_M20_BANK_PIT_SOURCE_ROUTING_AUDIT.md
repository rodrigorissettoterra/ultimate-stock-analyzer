# Post-M20 Bank Point-in-Time Source Routing Audit

## Purpose

Separate the bank model's inputs by evidence status instead of treating one
annual IFData profile as an all-or-nothing point-in-time object.

## Proven observed PIT routes

The version-aware CVM IPE Pillar 3 ledger provides observed filing timelines for:

- Basel ratio;
- Tier 1 ratio;
- CET1 / Capital Principal;
- leverage ratio.

For the current ten-input bank prudential coverage contract, Basel and Tier 1
represent 20% of critical inputs. In the structural bank model they represent
16% of total model weight.

## Timestamped CVM candidates

Official CVM DFP consolidated files expose receipt timestamps for total assets,
equity and consolidated net income. The audit validates one **consecutive**
current/prior fiscal-year pair so prior-balance dependencies are not claimed from
a gapped window.

These fields remain diagnostic candidates only because:

- the CVM issuer-accounting perimeter has not been proven equivalent to the BCB
  prudential-conglomerate perimeter;
- completeness of historical DFP re-presentation/vintage history in the bulk
  archive has not been proven.

Counting these timestamped candidates together with validated Pillar 3 fields
gives 70% of the ten-input critical contract and 37.5% of structural model
weight. Neither figure is a readiness score.

A five-year net-income CAGR is **not** included in candidate model coverage. The
bank growth contract needs six consecutive annual observations (`Y-5` through
`Y`), while this source-routing smoke validates only a two-year current/prior
pair.

## Still unresolved for strict PIT

- gross credit portfolio and its prior-year value;
- annual credit-loss result;
- net interest margin;
- 90-day NPL ratio and NPL coverage;
- efficiency and fee-income fields currently sourced from latest-state IFData;
- loan growth derived from the unresolved credit portfolio;
- six-year net-income window required for five-year net-income CAGR.

Dividend metrics remain outside this bank-accounting PIT audit and retain their
own evidence lifecycle.

## Readiness boundary

The audit keeps the following blockers active:

- `BANK_EVIDENCE_NOT_POINT_IN_TIME`;
- `BANK_SCOPE_ALIGNMENT_UNPROVEN`;
- `BANK_GROSS_CREDIT_PIT_SOURCE_UNRESOLVED`;
- `BANK_CREDIT_LOSS_PIT_SOURCE_UNRESOLVED`;
- `BANK_NET_INCOME_GROWTH_PIT_WINDOW_UNPROVEN`;
- `BANK_MODEL_PIT_COVERAGE_INCOMPLETE`;
- `CVM_DFP_REVISION_HISTORY_COMPLETENESS_UNPROVEN`;
- `PILLAR3_IPE_REVISION_HISTORY_COMPLETENESS_UNPROVEN`.

No scoring or historical-backtest readiness is promoted by this block.
