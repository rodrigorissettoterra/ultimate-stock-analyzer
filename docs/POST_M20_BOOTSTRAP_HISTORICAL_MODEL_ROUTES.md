# Post-M20 — Persist historical model routes into bootstrap runs

## Goal

Persist point-in-time `HistoricalModelRoute` records into an already completed
public-data bootstrap run without downloading FCA a second time.

## Contract

The persistence stage:

- requires a `COMPLETE` bootstrap manifest;
- is currently bounded to runs with an explicit ticker filter;
- reuses the manifest-bound `cvm_fca_raw` artifact for each year;
- verifies raw and normalized security artifact checksums before use;
- derives the exact CVM company identities from the normalized FCA security artifact;
- constructs the concrete `FCAHistoricalModelRouteSource` internally instead of accepting a pluggable materializer;
- accepts only the repository-approved FCA mapping content SHA-256 `2160ff0f9302aeb96992d19ba9bbd8483d429d2a4405a7450999d13ed3129c46` (`fca-sector-activity-v0.2`);
- accepts only the repository-approved sector registry content SHA-256 `51b54271624084bcff9bccd73178ab43f284811fbf5edcd35a305e03c1f1f171` (`0.6.3`);
- materializes routes through the validated FCA filing-ledger and approved mapping/registry contracts;
- revalidates returned mapping/registry provenance and exact official FCA document binding before persistence;
- rejects any materialization blocker, blocked company-year, coverage gap or non-PIT route;
- writes `cvm_historical_model_route` normalized artifacts only after all years pass;
- updates the manifest only after all route files are staged successfully;
- never uses the current B3 classification as a historical fallback.

The bounded ticker requirement is deliberate. The current explicit FCA mapping covers
the proven bank and commodities labels; it must not be interpreted as full-market
historical taxonomy coverage.

The configuration hashes are also deliberate. A file with the same textual version
but different mapping or registry contents is not trusted for this persistence stage.
Changing either approved file therefore requires an explicit, versioned code change
that updates the trust binding and passes review again.

## Transaction semantics

All company-years are materialized in memory before persistent state changes. Route
files are staged first, then moved into their final paths, and finally the manifest is
atomically replaced. If the final manifest update fails, newly created route files are
removed and the original manifest bytes are restored.

## Dataset access

`BootstrapDataset.historical_model_routes()` validates the persisted records through
`HistoricalModelRouteRegistry`, preserving exact company-year uniqueness and the
no-fallback point-in-time contract.

## Live smoke

The dedicated smoke downloads the official 2025 FCA archive exactly once, binds that
archive into a minimal completed bootstrap manifest, persists routes for Vale,
Petrobras and Itaú, and verifies:

- `cvm:4170` -> `commodities`;
- `cvm:9512` -> `commodities`;
- `cvm:19348` -> `banks`;
- exact proven `available_from` timestamps;
- PIT eligibility;
- the approved mapping and sector-registry hashes;
- manifest/artifact checksums;
- no custom route-source injection;
- no current-B3 fallback.

This block persists routing evidence only. It does not yet promote M16/readiness or
change the profiler's contract selection.