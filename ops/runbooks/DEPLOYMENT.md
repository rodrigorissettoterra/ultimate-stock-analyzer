# Deployment Runbook

## Preconditions

- Docker Engine with Compose;
- a private `.env` created from `.env.example`;
- a strong `POSTGRES_PASSWORD`;
- `USA_DATABASE_URL` pointing to the `postgres` service when using Compose;
- optional `USA_LLM_API_KEY` and `USA_LLM_MODEL` for LLM synthesis.

Never paste secrets into issues, commits, screenshots or CI logs.

## First deployment

1. Copy `.env.example` to `.env` and set secrets locally.
2. Use a URL-safe PostgreSQL password or percent-encode it in `USA_DATABASE_URL`.
3. Run `docker compose config` and verify that no unexpected public database port exists.
4. Run `docker compose build`.
5. Run `docker compose up -d`.
6. Verify `/health`, then `/ready`, then `/dashboard/`.
7. Check `docker compose logs --tail=100 api maintenance` for structured startup/runtime events.

The PostgreSQL initialization migration runs automatically only on a new empty volume. For an
existing database, apply reviewed migrations explicitly before replacing the API container.

## Rollback

Keep the previous image/commit SHA. Roll back application containers first; do not downgrade the
database schema unless the migration has a tested reverse path. Restore a database backup only when
schema/data damage actually requires it.

## Production truthfulness

A healthy deployment means the service and persistence layer are operational. It does **not** mean
a complete current B3/CVM dataset has been loaded or that M16 has empirically promoted model weights.
Those are separate data/model validation gates.
