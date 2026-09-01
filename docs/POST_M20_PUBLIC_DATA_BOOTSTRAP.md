# Post-M20 Gate — Public Data Bootstrap

Status: **implemented**.

This gate begins the empirical phase after the M0-M20 engineering foundation. It does not create or promote investment rankings. It materializes historical public-source inputs needed by later evidence, coverage and validation gates.

## Purpose

Create an auditable local dataset that preserves both:

1. the exact official source payload downloaded during the run; and
2. normalized records consumed by deterministic engines, with point-in-time limitations kept explicit.

The bootstrap is intentionally restricted to **completed calendar years** because the annual B3 COTAHIST archive is a historical input, not the live/current-price path.

## Core sources

- **CVM** `cad_cia_aberta.csv` — issuer master, including cancelled registrations to reduce active-only survivorship filtering.
- **CVM FCA** annual ZIP — ticker/security identity and historical listing metadata.
- **CVM DFP** annual ZIP — BPA, BPP, DRE, DFC_MI, DFC_MD and DVA normalized with document receipt timing.
- **B3 COTAHIST** annual ZIP — official raw historical quotes. They are preserved unadjusted for corporate actions.

## Optional current/specialized enrichments

The bootstrap can additionally materialize:

- **B3 current industry classification** and company-catalog identity, used for current diagnostic routing only. The workbook is a collection-time snapshot and is explicitly **not point-in-time eligible** for historical routing/walk-forward use.
- **BCB IFData prudential bank profiles**, resolved through exact prudential identity/account contracts. Historical API rows are latest-state observations without revision history and remain **not point-in-time eligible** for strict historical backtests.

These enrichments improve current structural diagnostics without changing their historical semantics.

Dividend/JCP history, corporate-action adjustment, current/live prices, securities-lending downloads, news and macro enrichment remain separate evidence paths because they have different publication frequencies and point-in-time semantics.

## Command

Full universe for a completed multi-year range:

```bash
ultimate-stock-analyzer bootstrap-public-data \
  --start-year 2021 \
  --end-year 2025 \
  --data-dir ./data
```

Selected tickers for a faster validation run:

```bash
ultimate-stock-analyzer bootstrap-public-data \
  --start-year 2023 \
  --end-year 2025 \
  --ticker PETR4 \
  --ticker VALE3 \
  --data-dir ./data
```

Post-M20 diagnostic scripts can invoke the same service with current B3 classification and IFData enabled when those source-contract boundaries need to be audited.

## Output

Each run is isolated under:

```text
data/bootstrap/<run_id>/
  manifest.json
  raw/
    cvm/
      cad_cia_aberta.csv
      fca_cia_aberta_<year>.zip
      dfp_cia_aberta_<year>.zip
    b3/
      COTAHIST_A<year>.ZIP
      ClassifSetorial.xlsx                  # optional
      company_catalog_pages.zip            # optional
    bcb/ifdata/...                          # optional
  normalized/
    cvm/
      issuers.jsonl.gz
      securities_<year>.jsonl.gz
      dfp_<year>.jsonl.gz
    b3/
      cotahist_<year>.jsonl.gz
      industry_classification_current.jsonl.gz  # optional
    bcb/
      ifdata_bank_profiles_<year>.jsonl.gz      # optional
```

`manifest.json` records source policy, requested tickers, statement set, row counts, byte sizes and SHA-256 for every materialized artifact, plus whether optional current classification/IFData evidence was included.

## Failure behavior

The runner is fail-closed. A required source failure raises an error and writes a `FAILED` manifest containing the artifacts already materialized plus the error. It never marks a partial run as complete.

## Point-in-time boundary

Historical-looking rows are not automatically declared PIT. CVM filing lines can carry receipt/publication timing; current B3 classification and latest-state IFData explicitly cannot. Raw COTAHIST quotes are historical but remain unadjusted.

The separate Historical Backtest Readiness Audit consumes these contracts and reports whether a particular bootstrap run is safe to feed into strict M15/M16 evaluation.

## Why this precedes live ranking

The integrated decision model requires Structural, Valuation and Entry components to be rankable. A financial statement download alone is insufficient. This gate establishes the auditable historical evidence layer first; subsequent gates must prove coverage, routing applicability, corporate-action/return correctness and point-in-time readiness before real backtests or weight promotion are trusted.
