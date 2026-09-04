# Post-M20 — Persist historical model routes into bootstrap runs

## Goal

Persist point-in-time `HistoricalModelRoute` records into an already completed
public-data bootstrap run without downloading FCA a second time.

## Contract

The persistence stage:

- requires a `COMPLETE` bootstrap manifest;
- is currently bounded to runs with an explicit ticker filter;
- reuses the manifest-bound `cvm_fca_raw` artifact for each year;
- consumes FCA/security artifacts from the exact bytes that passed manifest
  size/SHA-256 verification;
- rejects artifact paths that escape the run or use symlinked path components;
- derives exact CVM company identities from the verified normalized security bytes;
- accepts only the repository-approved FCA mapping content SHA-256
  `2160ff0f9302aeb96992d19ba9bbd8483d429d2a4405a7450999d13ed3129c46`
  (`fca-sector-activity-v0.2`);
- accepts only the repository-approved sector registry content SHA-256
  `51b54271624084bcff9bccd73178ab43f284811fbf5edcd35a305e03c1f1f171`
  (`0.6.3`);
- parses both trusted configuration objects from the same immutable bytes that
  passed those hash bindings, eliminating verify-then-reopen races;
- materializes routes through the validated FCA filing-ledger and approved
  mapping/registry contracts;
- revalidates returned mapping/registry provenance and exact official FCA
  document binding before persistence;
- rejects any materialization blocker, blocked company-year, coverage gap or
  non-PIT route;
- never uses current B3 classification as a historical fallback.

The bounded ticker requirement is deliberate. The current explicit FCA mapping
covers the proven bank and commodities labels; it must not be interpreted as
full-market historical taxonomy coverage.

## Publication and recovery semantics

Route files are serialized deterministically (`gzip` mtime `0`). This makes an
orphan route artifact left by a process interruption safely recognizable on a
retry: exact expected bytes are reused; different bytes fail closed.

New route artifacts and the manifest are written through randomized,
exclusively-created staging files. Predictable `.tmp` paths are never used.
Existing output symlinks, manifest symlinks and non-regular publication targets
are rejected rather than followed.

Before the manifest commit, the stage re-reads every FCA/security input through
the no-follow regular-file boundary and requires the bytes to remain identical
to the verified snapshots. It also requires the manifest itself to remain
identical to the bytes originally loaded. If either changed concurrently, the
new route files from that invocation are removed and the manifest is left
unchanged.

The manifest replacement is the final atomic publication operation. If a
process terminates after route publication but before that operation, a later
invocation can recover the exact deterministic orphan files without manual
cleanup.

## Dataset access

`BootstrapDataset.historical_model_routes()` validates persisted records through
`HistoricalModelRouteRegistry`, preserving exact company-year uniqueness and
the no-fallback point-in-time contract.

## Live smoke

The dedicated smoke downloads the official 2025 FCA archive exactly once,
binds that archive into a minimal completed bootstrap manifest, persists routes
for Vale, Petrobras and Itaú, and verifies:

- `cvm:4170` -> `commodities`;
- `cvm:9512` -> `commodities`;
- `cvm:19348` -> `banks`;
- exact proven `available_from` timestamps;
- PIT eligibility;
- approved mapping and sector-registry hashes;
- manifest/artifact checksums;
- no custom route-source injection;
- no current-B3 fallback.

This block persists routing evidence only. It does not yet promote M16/readiness
or change the profiler's contract selection.
