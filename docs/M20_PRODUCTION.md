# M20 — Production Foundation

Status: **implemented and merged**.

M20 establishes the operational foundation needed to run the research system persistently without claiming that real-data ingestion and empirical model validation have already been completed.

The implementation was merged only after the Python CI suite, secret scan and production Docker image build passed.

## Added

- validated runtime settings with fail-closed production database requirement;
- JSON structured logs and request IDs;
- `/health` and repository-backed `/ready` endpoints;
- retryable maintenance-job primitive with `run_id`;
- PostgreSQL read/write adapter for versioned analysis/backtest snapshots;
- initial database migration;
- non-root API image with explicit production dependencies;
- PostgreSQL no longer exposes port 5432 by default;
- Docker health checks and restart policies;
- maintenance heartbeat process;
- CI Docker image build;
- deployment, backup/restore and incident runbooks;
- backup/runtime artifacts excluded from Git.

## Operational boundary

The current `maintenance` worker validates repository readiness and provides the retry/heartbeat runtime boundary. It is not presented as if every source collector were already scheduled and operating unattended.

## What M20 deliberately does not claim

- that all B3/CVM historical data is already populated in PostgreSQL;
- that scheduled collectors are already operating unattended against every source;
- that M16 has found and promoted empirically superior weights;
- that a live deployment has already accumulated enough operational history to prove recovery/freshness objectives;
- that this repository is individualized financial advice.

Those require real operational data runs and validation, not additional architecture labels.

See also [`QUICKSTART.md`](QUICKSTART.md) and [`BACKLOG.md`](BACKLOG.md).
