# Post-M20 Gate — Public Data Bootstrap

Status: **implementation candidate**.

This gate begins the empirical phase after the M0-M20 engineering foundation. It does not create or promote investment rankings. It materializes the historical public-source inputs needed to run those models with real data.

## Purpose

Create an auditable local dataset that preserves both:

1. the exact official source payload downloaded during the run; and
2. the normalized point-in-time records consumed by the deterministic engines.

The bootstrap is intentionally restricted to **completed calendar years** because the annual B3 COTAHIST archive is a historical input, not the live/current-price path.

## Sources in this gate

- **CVM** `cad_cia_aberta.csv` — issuer master, including cancelled registrations to avoid active-only survivorship filtering.
- **CVM FCA** annual ZIP — ticker/security identity and historical listing metadata.
- **CVM DFP** annual ZIP — BPA, BPP, DRE, DFC_MI, DFC_MD and DVA normalized with document receipt timing.
- **B3 COTAHIST** annual ZIP — official raw historical quotes. B3 states that these prices are not adjusted for corporate events, so the bootstrap preserves them unadjusted.

Dividend/JCP history, current/live price, securities-lending downloads, news and macro enrichment remain separate gates because they have different publication frequencies and point-in-time semantics.

## Command

Full universe for 2021-2025:

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
  normalized/
    cvm/
      issuers.jsonl.gz
      securities_<year>.jsonl.gz
      dfp_<year>.jsonl.gz
    b3/
      cotahist_<year>.jsonl.gz
```

`manifest.json` records source policy, requested tickers, statement set, row counts, byte sizes and SHA-256 for every materialized artifact.

## Failure behavior

The runner is fail-closed. A required source failure raises an error and writes a `FAILED` manifest containing the artifacts already materialized plus the error. It never marks a partial run as complete.

## Why this precedes live ranking

The integrated decision model requires Structural, Valuation and Entry components to be rankable. A financial statement download alone is insufficient. This gate establishes the historical evidence layer first; subsequent gates will derive universe metrics, add corporate-action adjustments/current market data and only then persist `StockAnalysis` snapshots for the API/dashboard.
