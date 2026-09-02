# Post-M20 Gate — Fundamental Coverage Profiler

Status: **implemented**.

This gate consumes one verified `COMPLETE` Public Data Bootstrap run and measures whether normalized accounting evidence is sufficient for later deterministic metrics and point-in-time backtesting.

It does **not** produce an investment score.

## Checks

For each issuer/reference year the profiler reports:

- extracted fixed accounts;
- critical account coverage for the applicable accounting contract;
- total contract coverage;
- missing critical and supporting accounts;
- critical accounts that exist but lack publication timing;
- point-in-time critical coverage;
- mapped historical tickers;
- source documents;
- prior-fiscal-year availability;
- whether a two-year point-in-time pair is available for longitudinal metrics;
- current sector/subsector/segment context when the bootstrap includes the B3 snapshot;
- current sector-model selection when a `SectorModelRegistry` is supplied;
- whether specialized bank/insurance accounting evidence is available or still required.

## Sector/applicability boundary

The bootstrap can materialize the official B3 sector/subsector/segment workbook and company catalog. That enrichment resolves **current** economic-model applicability, but the B3 workbook remains a collection-time snapshot.

Consequently, current sector/model resolution and historical point-in-time eligibility are separate fields. A record can legitimately have a resolved `sector_model_id` while:

```text
sector_classification_point_in_time_eligible = false
```

The profiler never converts that current classification into historical routing evidence.

For banks, the profiler uses the verified BCB IFData accounting contract when a matching prudential profile exists. Because IFData historical API rows are latest-state observations without revision history, bank critical coverage can be structurally complete while point-in-time critical coverage remains zero for strict historical backtests.

Insurance and any other specialized model without its required accounting evidence remain visibly marked as requiring a specialized contract rather than silently falling back to general-corporate accounting.

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

`critical_coverage = 1.0` means all critical account names for the selected diagnostic/accounting contract were extracted.

`point_in_time_critical_coverage = 1.0` is stricter: every critical input also satisfies the source's PIT timing contract. For CVM corporate filings this requires traceable `available_from` timing. Latest-state specialized evidence such as current IFData history remains non-PIT even when its accounting values are otherwise complete.

`longitudinal_pair_ready = true` requires the current and immediately prior fiscal years to both have 100% point-in-time critical coverage. It is a conservative readiness gate for metrics that require beginning/end balance-sheet values.

## Relationship to historical backtesting

Coverage is necessary but not sufficient for M15/M16. Historical routing must also be PIT, security/price history must be complete, and returns must handle corporate actions correctly. The Post-M20 Historical Backtest Readiness Audit combines those source-contract checks and fails closed when a current-only or unadjusted input would leak into a historical simulation.
