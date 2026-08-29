# Post-M20 Gate — Fundamental Coverage Profiler

Status: **implementation candidate**.

This gate consumes one verified `COMPLETE` Public Data Bootstrap run and measures whether the normalized accounting evidence is sufficient for later deterministic metrics and point-in-time backtesting.

It does **not** produce an investment score.

## Checks

For each issuer/reference year the profiler reports:

- extracted fixed accounts;
- critical account coverage for `general_corporate_v1`;
- total contract coverage;
- missing critical and supporting accounts;
- critical accounts that exist but lack `available_from` publication timing;
- point-in-time critical coverage;
- mapped historical tickers;
- source documents;
- prior-fiscal-year availability;
- whether a two-year point-in-time pair is available for longitudinal metrics.

## Sector boundary

The bootstrap currently materializes CVM issuer/security/DFP data and B3 historical quotes, but it does not yet materialize B3 sector/subsector/segment classification.

Therefore every profile is explicitly marked:

```text
UNRESOLVED_SECTOR_CLASSIFICATION
```

The profiler uses the general-corporate contract strictly as a **coverage diagnostic**, not as a claim that the model applies to banks, insurers or every issuer. Sector-specific readiness will only be asserted after the classification enrichment gate.

## Integrity

`BootstrapDataset` verifies:

- bootstrap status is `COMPLETE`;
- every manifest artifact exists;
- byte size matches the manifest;
- SHA-256 matches the manifest;
- normalized row count matches the manifest when loaded.

A corrupted or partial bootstrap cannot silently enter the profiler.

## Command

```bash
ultimate-stock-analyzer profile-coverage \
  --run-dir ./data/bootstrap/<run_id> \
  --data-dir ./data
```

Output:

```text
data/coverage/<run_id>/
  fundamental_coverage.jsonl.gz
  summary.json
```

The derived output is separate from the bootstrap directory so the raw/bootstrap run remains immutable.

## Interpretation

`critical_coverage = 1.0` means all critical account names for the diagnostic contract were extracted.

`point_in_time_critical_coverage = 1.0` is stricter: every critical account also has a traceable publication timestamp (`available_from`). This is the relevant prerequisite for avoiding look-ahead leakage.

`longitudinal_pair_ready = true` requires the current and immediately prior fiscal years to both have 100% point-in-time critical coverage. It is a conservative readiness gate for metrics that require beginning/end balance-sheet values.
