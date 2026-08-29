# Post-M20 Gate — Real Public-Data Smoke Test

Status: **implementation candidate**.

This gate validates that the already implemented Public Data Bootstrap works against the live public endpoints currently exposed by CVM and B3.

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

## Coverage is diagnostic, not a failure threshold

The workflow intentionally does not fail because:

- the general-corporate accounting contract is incomplete for a company;
- `available_from` is missing for some accounting lines;
- a bank such as `ITUB4` has low coverage under the general-corporate diagnostic contract.

Those are empirical findings that the next data-model gates must address.

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

The next gate should be selected from the observed diagnostics, not assumed in advance. In particular:

- incomplete point-in-time timestamps -> improve CVM publication metadata lineage;
- unresolved sector applicability -> materialize B3 sector/subsector/segment classification;
- otherwise -> proceed to historical metric derivation and valuation/entry prerequisites.
