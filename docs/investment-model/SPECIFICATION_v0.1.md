# Investment Model Specification v0.1

This specification defines the initial scoring contract. Weights are hypotheses to be validated by point-in-time backtesting; they are not fitted to future returns yet.

## Output dimensions

- **Company Quality Score**: long-horizon health/quality of the business.
- **Investment Score**: quality plus current valuation and contextual factors.
- **Entry Score**: short-horizon attractiveness and speculation avoidance.
- **Final Score**: ordering signal for research prioritization.
- **Data Confidence**: coverage, source quality, freshness and conflict confidence.

## Quality categories

| Category | Initial weight | Examples |
|---|---:|---|
| Profitability | 18% | ROE, ROIC, EBIT margin, net margin |
| Financial strength | 16% | net debt/EBITDA, interest coverage, liquidity, debt/equity |
| Cash flow | 12% | cash conversion, FCF yield, FCF margin |
| Growth | 10% | revenue/EPS/FCF CAGR |
| Accounting quality | 10% | accrual quality, Piotroski, Beneish, earnings-cash consistency |
| Dividends | 12% | regularity, median DY, dividend growth, payout sustainability |
| Capital allocation | 8% | reinvestment, buybacks, dilution, ROIC vs cost of capital |
| Governance | 8% | listing/governance evidence, board/control/conflict indicators |
| Predictability | 6% | stability of revenue, margins, ROIC, FCF and dividends |

## Investment composition

The initial deterministic formula gives fundamentals dominance. Valuation is meaningful but cannot turn a structurally poor company into a top result. News, lending, macro and liquidity are modifiers. Risk and short pressure are explicit penalties.

## Entry model

Entry is independent of company quality and combines valuation context, distance from long moving averages, RSI attractiveness and a transparent speculation-risk heuristic. Material events may explain price/volume jumps and reduce false speculation flags.

## Dividend eligibility

Initial definition: positive regular dividend/JCP payments in at least 4 of the last 5 calendar years, with no gap above approximately 18 months between regular distributions. Extraordinary distributions are tracked separately and do not establish regularity.

## Red flags / veto examples

Potential blocking conditions include adverse auditor opinion, confirmed default, judicial recovery, severe accounting fraud evidence, structurally negative equity, unavailable/stale critical financial data, existential regulatory events and impractical liquidity. Exact production rules require evidence and sector-aware validation.

## Model development rule

A metric enters production only with: formula, source, unit, direction, sector applicability, missing-data behavior, tests, versioning and backtest evidence where appropriate.
