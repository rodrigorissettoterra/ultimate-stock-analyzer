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

## Technical completion

The repository implementation is complete through M20. Post-M20 work established the historical
evidence contracts needed to decide when strict M15/M16 execution is admissible without weakening
point-in-time rules.

Resolved Post-M20 implementation work includes:

- public-data bootstrap and immutable local lineage manifests;
- fundamental/publication-timing coverage profiling;
- historical security/universe evidence;
- historical sector/model routing from CVM/FCA evidence, with current-B3 fallback forbidden for
  historical decisions;
- raw COTAHIST provenance and event-aware M15 integration;
- validated share-action, cash-distribution and subscription-right economic-value handling;
- bounded historical readiness auditing that preserves source-specific blockers instead of silently
  fabricating historical evidence;
- bank, Pillar 3, CVM/IPE and B3 source-contract audits documenting exactly what the public sources
  do and do not prove.

See [`PROJECT_COMPLETION.md`](PROJECT_COMPLETION.md) for the closure contract.

## Accepted external data constraints

The following are **not unfinished architecture or code milestones**. They are external evidence
constraints that correctly keep strict empirical promotion fail-closed:

- **Bank/specialized history:** the free public IFData/related BCB surfaces provide useful reference
  periods and publication timing but do not expose a revision-aware historical replay contract for
  arbitrary simulated `as_of` dates. `BANK_EVIDENCE_NOT_POINT_IN_TIME` therefore remains a valid
  abstention condition.
- **B3 corporate actions:** raw COTAHIST plus the public company-supplement surface can validate
  observed event mechanics, but the free public contract does not prove that the observed events are
  an exhaustive immutable historical event ledger. Historical source-completeness blockers therefore
  remain valid.
- **CVM/IPE revision replay:** public IPE evidence retains versions, but the open annual ZIP chain is
  not documented as an immutable exhaustive snapshot for arbitrary past cutoffs and does not expose
  all timing/status semantics needed to infer such a contract.

These constraints must be resolved only by stronger evidence or a demonstrably better source. They
must never be removed merely to make a backtest run.

## Empirical and operational follow-up

The items below are activities performed **after technical project completion** and do not reopen the
implementation unless they expose a defect or require a material product change:

- materialize broader local historical datasets when admissible PIT evidence becomes available;
- execute strict full-history M15 runs only on datasets that pass the readiness gate;
- run M16 walk-forward calibration and promote weights only when repeated OOS gates pass;
- operate source collectors on the cadence chosen by the deployment environment;
- perform measured PostgreSQL backup/restore drills and record actual RPO/RTO;
- accumulate production freshness, availability and source-divergence history;
- evaluate a paid data source only if a free-first alternative is demonstrably inadequate;
- obtain regulatory/legal review before positioning the software publicly as an investment-analysis
  service rather than research software.

Until stronger empirical evidence exists, the versioned baseline model remains the research
configuration and the system abstains where strict PIT evidence is unavailable.
