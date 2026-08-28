# Architecture v0.1

## Goal

Build an auditable decision-support engine for B3 equities with two time horizons: structural company/investment analysis and short-horizon entry timing. Textual AI is isolated from authoritative numeric calculation.

## Logical layers

1. **Sources** — CVM, B3, BCB, IBGE/Ipea, issuer IR, open financial media, optional Fundamentus cross-check.
2. **Ingestion** — immutable raw downloads with checksums and collection timestamps.
3. **Normalization** — canonical company/security identifiers, units, currencies, restatements and point-in-time availability.
4. **Feature engines** — fundamentals, dividends, accounting quality, governance, capital allocation, valuation, market, risk, lending, macro, news/events.
5. **Scoring** — sector-aware deterministic normalization and versioned weights.
6. **Validation** — data quality, unit tests, backtests, walk-forward and stress tests.
7. **Serving** — API, dashboard and conversational explanation layer.

## Data stores

- PostgreSQL: canonical entities, observations, model versions and operational state.
- Parquet: immutable/high-volume historical datasets.
- DuckDB: local analytical and backtesting queries over Parquet.
- Object storage later when necessary; local filesystem is sufficient for development.

## Point-in-time invariant

A model run at time `T` may only use observations with `available_from <= T`. Restatements create new revisions instead of mutating history. Raw inputs are content-addressed where practical.

## LLM boundary

Allowed: classify materiality, event type, impact, severity, confidence; summarize evidence; answer questions grounded in retrieved documents.

Forbidden: invent missing financial values, silently resolve source conflicts, compute the official score, execute trades, or present uncertain text as fact.

## Failure philosophy

Missing data reduces coverage/confidence. Conflicting sources reduce conflict confidence. Severe red flags can veto positive classifications. The system may return `WATCH` or `BLOCKED` rather than force a recommendation.
