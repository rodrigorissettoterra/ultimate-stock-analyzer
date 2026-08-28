# M3 — Fundamental Metrics and CVM Account Contracts

## Objective

M3 expands the deterministic fundamental engine and binds common corporate inputs to fixed,
auditable CVM account codes. No LLM is used for authoritative calculations.

## Metric families

The engine now provides deterministic formulas for:

- growth (YoY and CAGR);
- margins (gross, EBIT, EBITDA, net, CFO and FCF);
- returns (ROE, ROA, ROIC, ROCE and ROIC spread);
- tax/NOPAT;
- liquidity (current, quick and cash ratios);
- leverage and solvency;
- working capital;
- cash flow and payout sustainability;
- operating efficiency;
- cash conversion cycle;
- predictability support via coefficient of variation.

## Fixed CVM account contract

For general non-financial companies the extractor uses exact standardized CVM account codes,
including examples such as:

| Canonical input | Statement | CVM account |
|---|---|---|
| total assets | BPA | `1` |
| current assets | BPA | `1.01` |
| cash and equivalents | BPA | `1.01.01` |
| financial investments | BPA | `1.01.02` |
| receivables | BPA | `1.01.03` |
| inventories | BPA | `1.01.04` |
| current liabilities | BPP | `2.01` |
| suppliers | BPP | `2.01.02` |
| current borrowings | BPP | `2.01.04` |
| non-current borrowings | BPP | `2.02.01` |
| equity | BPP | `2.03` |
| revenue | DRE | `3.01` |
| gross profit | DRE | `3.03` |
| EBIT | DRE | `3.05` |
| pre-tax income | DRE | `3.07` |
| income tax | DRE | `3.08` |
| parent net income | DRE | `3.11.01` |
| operating cash flow | DFC | `6.01` |
| depreciation/amortization | DVA | `7.04.01` |

The extractor retains the original `FinancialStatementLine` for every extracted value so a metric
can be traced back to its CVM document, version and availability timestamp.

## No silent fuzzy matching

Company-specific non-fixed accounts are not mapped by text silently. If an indicator requires a
non-standard line (for example some CAPEX, lease or industry-specific components), the input stays
missing until an explicit, tested resolver is defined. This protects the score from plausible but
incorrect accounting guesses.

## Sector boundary

`general_corporate_v1` explicitly excludes banks and insurers. Their economically meaningful
capital, leverage, profitability and liquidity contracts are materially different and are handled
in M6 sector models.
