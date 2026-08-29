# Post-M20 Gate — Real Public-Data Smoke Test

Status: **validated against live official sources**.

This gate validates that the Public Data Bootstrap works against the live public endpoints currently exposed by CVM and B3.

It is deliberately bounded and does **not** publish the downloaded data lake.

## What the smoke test proves

For the latest completed calendar year, the workflow:

1. downloads the official CVM issuer registry;
2. downloads the annual CVM FCA and DFP archives;
3. downloads the annual B3 COTAHIST archive;
4. filters a small validation set (`PETR4`, `VALE3`, `ITUB4`);
5. verifies the bootstrap manifest and every materialized artifact checksum;
6. confirms every requested ticker is present in both the FCA security master and B3 historical quotes;
7. runs the Fundamental Coverage Profiler;
8. publishes only diagnostic JSON files.

A PASS means source access, parsing, integrity checks and bounded end-to-end materialization all worked.

It does **not** mean the investment model is calibrated or that every issuer is rankable.

## First validated live run

The first complete live-source PASS was executed on **2026-08-29** against the completed **2025** calendar year using `PETR4`, `VALE3` and `ITUB4`.

Bootstrap output:

- issuer records retained for the selected company identities: **5**;
- normalized securities: **3**;
- normalized DFP statement lines: **1,830**;
- B3 COTAHIST price bars: **750**;
- requested tickers found in FCA: **3/3**;
- requested tickers found in COTAHIST: **3/3**.

Fundamental coverage diagnostic:

- company-years profiled: **3**;
- mean critical-account coverage: **96.97%**;
- mean total-account coverage: **88.41%**;
- critical coverage at 100%: **2/3** company-years;
- critical coverage at 90–99%: **1/3** company-years;
- point-in-time critical-complete company-years: **0/3**;
- longitudinal pair-ready company-years: **0/3**, expected for a one-year smoke run.

The result establishes that raw public-source acquisition and accounting coverage are viable, while **publication/receipt timestamp lineage is the next correctness gate**. Historical ranking/backtesting must not proceed until the DFP `available_from` lineage is populated reliably, otherwise look-ahead bias is possible.

The live run also identified two FCA ticker rows (`INBR32`, `PNC`) that could not be joined to the official CVM issuer registry. They are preserved in the raw FCA archive, excluded from the normalized issuer-linked security layer, and surfaced as an audit warning. Requested tickers still fail closed if they cannot be resolved.

## Coverage is diagnostic, not a failure threshold

The workflow intentionally does not fail because:

- the general-corporate accounting contract is incomplete for a company;
- `available_from` is missing for some accounting lines;
- a bank such as `ITUB4` has lower coverage under the general-corporate diagnostic contract.

Those are empirical findings that subsequent data-model gates must address.

The workflow fails only for operational/data-contract problems such as inaccessible sources, missing requested tickers, empty required datasets, invalid checksums or parser failures.

## GitHub Actions

Workflow:

```text
.github/workflows/real-data-smoke.yml
```

It runs:

- manually through `workflow_dispatch`; and
- on pull requests that modify the smoke workflow or its public-data ingestion dependencies.

The pull-request trigger is intentional so endpoint/parser changes are validated before merge. The job is bounded to one completed year and three tickers.

The preflight checks current CVM/B3 network paths and derives the B3 COTAHIST year dynamically from the latest completed calendar year.

## Artifacts

Only these diagnostics are uploaded:

```text
smoke-artifacts/
  bootstrap_manifest.json
  coverage_summary.json
  smoke_summary.json
```

Raw CVM/B3 archives and normalized historical datasets remain ephemeral on the Actions runner and are not uploaded or committed.

Artifact retention is seven days.

## Interpretation

`smoke_summary.json` is the first file to inspect.

- `status = PASS`: source access, ticker presence, non-empty core datasets and integrity checks succeeded.
- `status = FAILED`: inspect `error` and `bootstrap_manifest.json`.
- `coverage`: empirical readiness metrics; these are not investment scores.

The next gate must be selected from observed diagnostics, not assumed in advance. The validated 2025 run selected **CVM DFP publication/receipt timestamp lineage** as the immediate next gate. Sector/subsector/segment materialization follows after point-in-time correctness is established.
