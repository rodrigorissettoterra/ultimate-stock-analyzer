# Incident Response Runbook

## Secret exposure

1. Treat the exposed credential as compromised even if the commit was quickly removed.
2. Revoke/rotate the credential at the provider.
3. Replace the runtime secret through the deployment secret mechanism.
4. Review Git history, CI logs and application logs for additional exposure.
5. Only then clean repository history if required; history rewriting is not credential rotation.

## Incorrect market/financial data

1. Mark affected analyses unavailable or `INCONCLUSIVE`; do not silently substitute another source.
2. Preserve the bad snapshot and lineage for diagnosis when legally allowed.
3. Identify source/version/date boundaries.
4. Reprocess into a new snapshot/revision.
5. Re-run regression tests and any affected backtests before republishing scores.

## LLM anomaly

Disable LLM synthesis by clearing runtime LLM key/model and restart the API. Deterministic agent mode
remains available. LLM output never changes stored scores, so an explanation incident should not
require recomputing financial metrics.

## Service outage

Check `/health`, `/ready`, PostgreSQL health, then structured logs by `request_id`/`run_id`. Prefer
rollback to an already validated image over live patching a production container.
