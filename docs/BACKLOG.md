# Backlog

- **M0 Foundation** — architecture, security, licensing and project contracts. **DONE.**
- **M1 Universe/CVM** — canonical issuers/securities and official registration data. **DONE.**
- **M2 Normalization** — point-in-time financial statements and revisions. **DONE.**
- **M3 Fundamental metrics** — deterministic accounting/financial metrics. **DONE.**
- **M4 Dividend Engine** — regularity, sustainability and official-event semantics. **DONE.**
- **M5 Structural Score** — sector-peer company quality. **DONE.**
- **M6 Sector models** — banks, insurers, utilities, commodities and corporates. **DONE.**
- **M7 Valuation** — multi-model fair-value ranges and margin of safety. **DONE.**
- **M8 Market/entry** — market context and speculation risk. **DONE.**
- **M9 Risk/liquidity** — downside risk and execution capacity. **DONE.**
- **M10 Accounting/governance** — quality, audit, governance and insider evidence. **DONE.**
- **M11 Securities lending** — B3 loan rates, utilization and short pressure. **DONE.**
- **M12 News/events + LLM** — dedupe, clustering, materiality and impact. **DONE.**
- **M13 Macro** — BCB/IBGE and sector sensitivity/scenarios. **DONE.**
- **M14 Integrated score** — company quality, investment attractiveness and entry timing. **DONE.**
- **M15 Backtesting** — point-in-time, corporate actions and benchmark comparison. **DONE.**
- **M16 Walk-forward** — calibration framework with strict OOS promotion gates. **DONE.**
- **M17 API** — stable read/query endpoints and persistence boundary. **DONE.**
- **M18 Dashboard** — ranking, company details and validation views. **DONE.**
- **M19 Conversational Agent** — evidence-backed retrieval and optional LLM synthesis. **DONE.**
- **M20 Production** — operational foundation, persistence, observability, container gates and runbooks. **DONE.**

## Post-M20 empirical/operational gates

These are validation and operations tasks rather than missing architecture milestones:

- populate a sufficiently complete point-in-time B3/CVM historical dataset;
- execute full historical backtests across multiple market regimes;
- run M16 walk-forward calibration and promote new weights only if OOS gates are met repeatedly;
- automate/schedule production collectors with source-specific monitoring and retry policies;
- validate real PostgreSQL backup/restore drills and operational recovery objectives;
- measure data coverage, freshness and source divergence in sustained runs;
- document any paid data source only if a free alternative is demonstrably inadequate;
- perform regulatory/legal review before presenting the system publicly as an investment-analysis service rather than research software.
