# M17 — Stable Query API

Status: **implemented in v1 API candidate**.

M17 turns the project into a queryable service without moving financial logic into the HTTP layer.

## Contracts

The stable namespace is `/v1`. The API exposes already-computed, versioned analysis results through
a repository abstraction. It does not accept arbitrary financial rows and recalculate investment
scores inside route handlers.

Endpoints:

- `GET /health`
- `GET /v1/meta`
- `GET /v1/ranking`
- `GET /v1/stocks/{ticker}`
- `GET /v1/stocks/{ticker}/scores`
- `GET /v1/backtests`
- `GET /v1/backtests/{backtest_id}`

## Ranking semantics

The primary ranking key is **Investment Attractiveness**, not Entry Timing or the legacy final
score. Entry remains visible as its own answer. Unrankable analyses are excluded by default but can
be requested explicitly for diagnostics.

## Persistence boundary

`AnalysisRepository` is the persistence contract. `InMemoryAnalysisRepository` is intentionally
provided for tests, notebooks and Google Colab. A PostgreSQL implementation can be added without
changing API schemas or routes.

## Public repository safety

Evidence objects expose provenance metadata and source URLs, not copied news corpora, credentials
or private payloads.

## API evolution

Breaking changes require a new URL namespace. Additive fields may be introduced in `/v1` while
preserving existing field meanings. Model versions are independent from the HTTP API version.
