# M6 — Sector Models

Status: **implemented in v0.6**.

## Objective

The structural score must compare businesses using economics that make sense for their
industry. Banks, insurers, utilities and commodity producers are not evaluated with the same
balance-sheet and operating metrics as a generic industrial company.

M6 adds a deterministic sector-model registry and routes each issuer to one of five model
families before structural scoring:

- `general_corporate_v1`
- `bank_v1`
- `insurance_v1`
- `utilities_v1`
- `commodities_v1`

The registry is versioned in `config/scoring/sector_registry_v0.6.yml`. Model weights and metric
definitions are versioned independently under `config/scoring/sectors/`.

## Routing rules

Routing uses only structured classification fields (`sector`, `subsector`, `segment`,
`industry`). Company-name heuristics are deliberately forbidden because they are difficult to
audit and can silently misclassify issuers.

Text matching is case-insensitive and accent-insensitive. Rules are evaluated by explicit
priority. If no specialized rule matches, the issuer falls back to the general corporate model.

The selected model, peer group and routing reason are returned with every structural result.

## Peer groups

Cross-sectional percentiles must be calculated against economically comparable companies.

- Banks: one banking peer pool unless a later model version introduces a finer taxonomy.
- Insurers: one insurance peer pool unless a later model version introduces a finer taxonomy.
- Utilities: prefer subsector, then sector.
- Commodities: prefer subsector, then segment, then sector.
- General corporates: sector.

Small peer groups continue to use the M5 shrinkage rule toward a neutral score of 50.

## Model design

### Banks

Corporate leverage metrics such as `net_debt_ebitda` are excluded. The v0.6 bank model uses:

- profitability: ROE, ROA, net interest margin;
- asset quality: 90-day NPL ratio, cost of credit, NPL coverage;
- capital: Basel ratio, Tier 1 ratio, equity/assets;
- efficiency: efficiency ratio and fee-income share;
- growth: loan and net-income growth;
- dividend quality: regularity, sustainability and growth.

Preferred free source for bank-specific prudential and credit metrics: **Banco Central do Brasil
IFData**, complemented by CVM filings.

### Insurers

The model emphasizes underwriting economics rather than industrial leverage:

- profitability: ROE and ROA;
- underwriting quality: combined, loss and expense ratios;
- capital: solvency, capital adequacy and technical-provision coverage;
- growth: premiums and net income;
- predictability: combined-ratio and earnings volatility;
- dividend quality.

Preferred free sources: **SUSEP** open/statistical/financial data plus CVM filings.

### Utilities

The model emphasizes leverage, cash-flow durability and predictability:

- ROIC, ROE and EBITDA margin;
- net debt/EBITDA, interest coverage, debt maturity and cash/debt;
- cash conversion, CFO margin and FCF margin;
- revenue/margin volatility and positive-FCF history;
- moderate growth weight;
- dividend quality.

### Commodities

The model uses cycle-aware history instead of rewarding one unusually strong commodity year:

- five-year median ROIC, ROE and EBITDA margin;
- balance-sheet resilience;
- five-year median FCF and CFO/capex;
- positive-FCF years;
- margin volatility, maximum margin drawdown and peak leverage;
- low weight for growth;
- dividend quality.

## Important limitation

The v0.6 weights are **economic hypotheses**, not optimized weights. They must not be presented
as empirically optimal until M15/M16 point-in-time backtesting and walk-forward calibration are
complete.

Missing specialized metrics do not get fabricated or imputed by the LLM. Existing coverage and
confidence gates remain active; an issuer with insufficient evidence is not ranked.
