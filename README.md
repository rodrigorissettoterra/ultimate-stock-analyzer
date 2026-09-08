# Ultimate Stock Analyzer

An open, free-first and auditable research engine for Brazilian equities. It separates three questions that are often incorrectly collapsed into a single rating:

1. **Company Quality** — is this a structurally good business?
2. **Investment Attractiveness** — is the security attractive at the current price?
3. **Entry Timing** — is the current market setup favorable for buying now?

Deterministic Python owns financial calculations, normalization, scoring, ranking and backtesting. LLMs are optional and restricted to evidence-backed analysis/synthesis of unstructured text.

> **Status: technical implementation complete.** Engineering milestones **M0-M20** and the Post-M20 evidence/readiness contracts are implemented. The project is complete as **auditable research software and decision-support infrastructure**. Historical point-in-time or source-completeness limitations that cannot be proven from the available public contracts remain explicit and fail-closed; they are not treated as unfinished engineering work. See [`docs/PROJECT_COMPLETION.md`](docs/PROJECT_COMPLETION.md).

> This is research software, not individualized investment advice and not a promise of future returns.

## Core principles

- **Evidence > model > LLM.** The LLM never becomes the source of truth for a financial number.
- **Free-first.** Official/public CVM, B3, Banco Central and other free sources come before paid providers.
- **Point-in-time.** Historical analysis uses what was actually available at each date, including publication/revision timing.
- **No silent fabrication.** Missing or conflicting observations reduce confidence or produce abstention/blocks.
- **Sector-aware.** Banks, insurers, utilities, commodity producers and non-financial corporates use different contracts where appropriate.
- **Auditable.** Scores remain decomposable into components, data confidence and evidence.
- **Public-by-design.** Real API keys, credentials, licensed datasets and private data must never be committed.
- **Backtest before trust.** Candidate weights are not promoted merely because they look better in-sample.

## What is implemented

### Data and fundamentals

- CVM issuer/security identity using stable `CD_CVM` contracts.
- DFP/ITR/FCA point-in-time ingestion and normalization with revisions and publication timing.
- Source-line lineage for normalized financial observations.
- Deterministic profitability, growth, leverage, liquidity, cash-flow, efficiency and quality metrics.
- Dividend/JCP regularity, sustainability, extraordinary-distribution detection and payout coverage.
- Sector-specific scoring foundations for financial and non-financial companies.
- Accounting quality, audit/governance, insider alignment and capital-allocation evidence.
- B3 securities-lending opportunity and short-pressure modeling.
- Banco Central macro collection and macro-sensitivity/scenario components.
- Fundamentus retained only as a complementary fallback/cross-check.

### Decision model

- Structural/company-quality score.
- Valuation and margin-of-safety components.
- Entry-timing and speculation-risk components.
- Liquidity and downside-risk components.
- News/event materiality with optional LLM classification.
- Rental opportunity versus short-pressure separation.
- Data-confidence score and fail-closed evidence rules.
- Integrated **Investment Attractiveness** model with explicit veto/block conditions.
- Separate **Entry Timing** output that cannot silently change the investment-attractiveness score.

### Validation

- Point-in-time backtesting with historical-universe membership to reduce survivorship bias.
- Publication-aware score visibility to prevent look-ahead leakage.
- Corporate-action-aware returns, costs/slippage and benchmark comparison.
- Walk-forward calibration framework with expanding windows, cross-sectional rank IC, baseline regularization and conservative out-of-sample promotion gates.
- Post-M20 bounded readiness audits that keep diagnostic evidence separate from strict readiness promotion.
- Raw COTAHIST preservation plus validated event-aware handling of supported distributions, share-ratio events and subscription-right economic value.

### Interfaces

- Versioned FastAPI `/v1` read/query API.
- Responsive dashboard served at `/dashboard/` and backed only by the API boundary.
- Evidence-grounded conversational agent at `POST /v1/agent/query`.
- Deterministic agent mode when no LLM key/model is configured.
- Optional OpenAI-compatible synthesis when local environment variables are configured.

### Production foundation

- PostgreSQL snapshot persistence boundary.
- `/health` and repository-backed `/ready` endpoints.
- Structured JSON logs, request IDs and retryable job primitives with `run_id`.
- Non-root production container.
- Hardened Docker Compose stack with PostgreSQL not publicly exposed by default.
- Docker image build gate in CI.
- Deployment, backup/restore and incident runbooks.
- Maintenance heartbeat/retry worker.

## Post-completion empirical and operational work

The repository implementation is complete, but production operation and empirical model promotion require evidence that cannot be manufactured by code. In particular:

- collectors must be run continuously in a chosen deployment environment to accumulate real freshness/availability/divergence history;
- real backup/restore drills must be executed to measure RPO/RTO;
- broader historical datasets should be materialized only when the required point-in-time source contracts are admissible;
- strict M15 studies should run only after the historical readiness gate accepts the underlying evidence;
- M16 candidate weights should be promoted only after repeated out-of-sample gates pass;
- paid historical data should be evaluated only if free-first sources are demonstrably inadequate;
- regulatory/legal review is required if the project is repositioned from research software to a public investment-analysis service.

Known public-source limitations remain explicit. For example, the currently audited public contracts do not prove every historical revision/vintage required for arbitrary past `as_of` replay in specialized bank evidence, CVM/IPE revision history or the complete B3 corporate-action ledger. The correct behavior is abstention or blocked strict readiness, not optimistic backfilling.

## Quick start

Python 3.12+:

```bash
python -m venv .venv
# Windows / PowerShell: .\.venv\Scripts\Activate.ps1
# Linux / macOS: source .venv/bin/activate
python -m pip install --upgrade pip
pip install -e ".[dev]"
ruff check src tests
pytest -q
uvicorn ultimate_stock_analyzer.api.main:app --reload
```

Then open:

- `http://127.0.0.1:8000/docs` — OpenAPI
- `http://127.0.0.1:8000/dashboard/` — dashboard
- `http://127.0.0.1:8000/v1/meta` — API/model semantics

A default development run uses the in-memory repository if `USA_DATABASE_URL` is empty, so it starts without persisted live market-analysis snapshots.

For complete setup instructions:

- **Local + Docker/PostgreSQL:** [`docs/QUICKSTART.md`](docs/QUICKSTART.md)
- **Google Colab:** [`docs/COLAB.md`](docs/COLAB.md)

Optional free Fundamentus adapter:

```bash
pip install -e ".[fundamentus]"
ultimate-stock-analyzer screen-dividends --min-dy 0.04 --max-candidates 50
```

Synthetic deterministic example:

```bash
python examples/demo_ranking.py
```

## API v1

Main endpoints:

```text
GET  /health
GET  /ready
GET  /v1/meta
GET  /v1/ranking
GET  /v1/stocks/{ticker}
GET  /v1/stocks/{ticker}/scores
GET  /v1/backtests
GET  /v1/backtests/{backtest_id}
POST /v1/agent/query
GET  /dashboard/
```

The HTTP layer exposes precomputed/versioned research outputs; it does not accept arbitrary raw financial rows from clients and recalculate authoritative scores inside request handlers.

## Repository layout

```text
src/ultimate_stock_analyzer/
  collectors/       official/public-source ingestion adapters
  normalization/    canonical point-in-time normalization
  fundamentals/     deterministic financial/accounting formulas
  dividends/        dividend/JCP regularity and sustainability
  valuation/        valuation and fair-value engines
  market/           price, entry and speculation context
  risk/             liquidity/downside risk components
  lending/          securities lending / short pressure
  news/             news/event evidence and LLM-assisted classification
  macro/            macro data and sensitivity engines
  scoring/          structural and integrated decision models
  backtesting/      point-in-time simulation, metrics and walk-forward calibration
  agent/            deterministic retrieval + optional LLM synthesis
  api/              FastAPI v1 contracts and query services
  web/              dependency-light dashboard
  runtime/          settings, logging, jobs and worker
  storage/          PostgreSQL snapshot repository
config/              versioned sector/scoring configuration
ops/                 migrations and operational runbooks
docs/                milestone specifications and guides
tests/               deterministic regression/unit tests
```

## Data and security policy

The Git repository is **not** the financial data lake. Raw/processed datasets, credentials, `.env`, API keys and operational backups are excluded from version control. Collectors are designed to reconstruct data from original sources while preserving lineage.

See:

- [`docs/PROJECT_COMPLETION.md`](docs/PROJECT_COMPLETION.md)
- [`DATA_SOURCES.md`](DATA_SOURCES.md)
- [`SECURITY.md`](SECURITY.md)
- [`DISCLAIMER.md`](DISCLAIMER.md)
- [`docs/BACKLOG.md`](docs/BACKLOG.md)
- [`docs/M15_BACKTESTING.md`](docs/M15_BACKTESTING.md)
- [`docs/M16_WALK_FORWARD.md`](docs/M16_WALK_FORWARD.md)
- [`docs/M20_PRODUCTION.md`](docs/M20_PRODUCTION.md)

## License

Code is licensed under the Apache License 2.0. Third-party data remains subject to the terms, licenses and rights of its original providers.
