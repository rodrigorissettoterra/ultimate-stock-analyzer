# PostgreSQL Backup and Restore Runbook

Backups contain derived analyses and may contain licensed/source-linked metadata. Store them outside
the public repository. `/backups/` and common dump extensions are ignored by Git.

## Backup

Create a local private directory, then run from the repository root:

```bash
mkdir -p backups
docker compose exec -T postgres sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > "backups/usa-$(date +%Y%m%d-%H%M%S).dump"
```

Encrypt/off-site-store production backups according to the deployment environment. Do not commit
backup files.

## Verification

A backup is not valid merely because `pg_dump` exited successfully. Periodically restore into an
isolated disposable database/container and verify table counts plus representative API reads.

## Restore

Stop write-producing jobs first. Restore into an empty compatible PostgreSQL database with
`pg_restore --clean --if-exists` only after confirming the target. Re-run `/ready` and representative
stock/backtest queries before re-enabling maintenance/data jobs.

## Suggested initial policy

- daily logical backup;
- retain 7 daily, 4 weekly and 3 monthly copies;
- document actual RPO/RTO after measured restore drills.
