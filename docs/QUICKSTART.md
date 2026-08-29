# Quick Start

This guide covers the supported development and local Docker paths for the Ultimate Stock Analyzer.

## Requirements

- Python 3.12+
- Git
- Docker + Docker Compose only if you want the PostgreSQL-backed local stack

The project is free-first. An LLM key is optional: without one, the conversational agent uses deterministic synthesis.

## 1. Local Python development

Clone the repository and create a virtual environment:

```bash
git clone https://github.com/rodrigorissettoterra/ultimate-stock-analyzer.git
cd ultimate-stock-analyzer
python -m venv .venv
```

Activate it:

```powershell
# Windows / PowerShell
.\.venv\Scripts\Activate.ps1
```

```bash
# Linux / macOS
source .venv/bin/activate
```

Install the development dependencies and run the gates:

```bash
python -m pip install --upgrade pip
pip install -e ".[dev]"
ruff check src tests
pytest -q
```

Start the API:

```bash
uvicorn ultimate_stock_analyzer.api.main:app --reload
```

Useful local URLs:

- `http://127.0.0.1:8000/health` — process health
- `http://127.0.0.1:8000/ready` — repository readiness
- `http://127.0.0.1:8000/docs` — OpenAPI/Swagger
- `http://127.0.0.1:8000/dashboard/` — dashboard
- `http://127.0.0.1:8000/v1/meta` — API/model semantics

With no `USA_DATABASE_URL`, the API intentionally uses the in-memory repository. That is useful for tests and development but starts without a persisted market-analysis dataset.

Run the synthetic example to exercise the deterministic scoring path:

```bash
python examples/demo_ranking.py
```

## 2. Optional LLM synthesis

Copy the environment template:

```powershell
# Windows / PowerShell
Copy-Item .env.example .env
```

```bash
# Linux / macOS
cp .env.example .env
```

Set only local values in `.env` and never commit that file:

```dotenv
USA_LLM_API_KEY=<your-local-key>
USA_LLM_MODEL=<your-model-name>
USA_LLM_BASE_URL=https://api.openai.com/v1
```

If `USA_LLM_API_KEY` or `USA_LLM_MODEL` is empty, the conversational agent remains deterministic. The LLM is allowed to synthesize evidence-backed text; it does not calculate or modify authoritative scores.

## 3. Docker + PostgreSQL

Create `.env` from `.env.example`, then set at minimum:

```dotenv
POSTGRES_DB=usa
POSTGRES_USER=usa
POSTGRES_PASSWORD=<strong-local-password>
USA_DATABASE_URL=postgresql://usa:<strong-local-password>@postgres:5432/usa
```

If the password contains URL-reserved characters, URL-encode it in `USA_DATABASE_URL`.

Build and start the stack:

```bash
docker compose up --build -d
```

Check service status:

```bash
docker compose ps
```

Check readiness:

```bash
curl http://127.0.0.1:8000/ready
```

The Compose stack contains:

- `postgres` — PostgreSQL 16, internal-only (no public host port)
- `api` — FastAPI, exposed on port 8000
- `maintenance` — operational heartbeat/retry worker

The initial PostgreSQL schema is mounted from `ops/migrations/001_initial.sql`.

Stop the stack without deleting the database volume:

```bash
docker compose down
```

To remove the local PostgreSQL volume as well:

```bash
docker compose down -v
```

## 4. API examples

Metadata:

```bash
curl http://127.0.0.1:8000/v1/meta
```

Ranking:

```bash
curl "http://127.0.0.1:8000/v1/ranking?limit=20"
```

One stock:

```bash
curl http://127.0.0.1:8000/v1/stocks/PETR4
```

Agent query:

```bash
curl -X POST http://127.0.0.1:8000/v1/agent/query \
  -H "Content-Type: application/json" \
  -d '{"question":"Compare the strongest available companies and explain the evidence."}'
```

The query endpoints return only data already present in the configured repository; they do not silently invent missing observations.

## 5. Important current limitation

M0-M20 complete the engineering and operational foundation, not the empirical validation of a live investment product. Before using results to support real-money decisions, the project still needs a sufficiently complete point-in-time historical dataset, production data population, full walk-forward evaluation and documented model-promotion evidence.

See also:

- [`COLAB.md`](COLAB.md)
- [`BACKLOG.md`](BACKLOG.md)
- [`M15_BACKTESTING.md`](M15_BACKTESTING.md)
- [`M16_WALK_FORWARD.md`](M16_WALK_FORWARD.md)
- [`M20_PRODUCTION.md`](M20_PRODUCTION.md)
