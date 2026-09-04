# Post-M20 — Persist historical model routes into bootstrap runs

## Goal

Persist point-in-time `HistoricalModelRoute` records into an already completed
public-data bootstrap run without downloading FCA a second time.

## Contract

The persistence stage:

- requires a `COMPLETE` bootstrap manifest;
- is currently bounded to runs with an explicit ticker filter;
- reuses manifest-bound `cvm_fca_raw` and security artifacts;
- consumes FCA/security artifacts from the exact bytes that pass manifest
  size/SHA-256 verification;
- rejects manifest, artifact and route-output symlinks instead of following them;
- keeps artifact and publication paths confined to the bootstrap run;
- parses both the FCA mapping and sector registry from the exact immutable bytes
  that pass their repository-approved SHA-256 bindings;
- retains mapping version `fca-sector-activity-v0.2` and sector-registry version
  `0.6.3` as explicit trust contracts;
- rejects materialization blockers, blocked company-years, coverage gaps,
  provenance mismatches and non-PIT routes;
- never uses current B3 classification as a historical fallback.

The bounded ticker requirement is deliberate. The explicit FCA mapping currently
covers only labels whose historical routing has been proven. It must not be
interpreted as full-market historical taxonomy coverage.

## Serialized publication transaction

Every invocation acquires one OS-held advisory publication lock inside the
bootstrap run before reading the manifest. The lock is held through routing,
staging, final validation and manifest replacement. Concurrent invocations of
this persistence stage therefore cannot both plan from the same manifest or
replace the same route output.

The lock file is persistent, but the lock itself belongs to the open file
descriptor and is released automatically by the operating system if the process
terminates. The lock path must be a regular non-symlink file.

Route files are serialized deterministically (`gzip` mtime `0`). This makes an
orphan route artifact left by an interruption recognizable on retry: exact
expected bytes are reused; different bytes fail closed.

New route artifacts and the manifest are written through randomized,
exclusively-created staging files. Predictable `.tmp` names are never used.
Once a route artifact has been moved to its final path it is deliberately not
removed by a later rollback. Filesystems can reuse inode identities immediately,
so attempting to prove post-close ownership is unsafe. If the manifest commit
fails, the old manifest remains authoritative and the deterministic route file is
left as an orphan. A retry reuses it only when its bytes exactly match the
expected artifact; conflicting bytes fail closed.

The new manifest staging file is completely written and fsynced before the final
commit window. While the run lock remains held, the stage then revalidates every
FCA/security input snapshot, the original manifest bytes, and each route output.
The immediately following operation is the atomic manifest replacement. Any
change detected in that protected window aborts publication.

## Verified dataset reads

`BootstrapDataset` does not rely on an earlier verification when it later parses
an artifact. Each accessor reopens the artifact through the no-follow,
run-confined regular-file boundary, verifies size and SHA-256 against the
manifest, and parses those same verified bytes. This applies to persisted
historical routes as well as the existing normalized bootstrap models.

`BootstrapDataset.historical_model_routes()` additionally validates route
company-year uniqueness through `HistoricalModelRouteRegistry`.

## Live smoke

The dedicated smoke downloads the official 2025 FCA archive exactly once,
binds that archive into a completed bootstrap manifest, persists routes for
Vale, Petrobras and Itaú, and verifies:

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
