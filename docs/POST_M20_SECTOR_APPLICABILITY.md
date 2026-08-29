# Post-M20 — B3 sector applicability gate

## Objective

Materialize the official current B3 economic classification so the existing sector-model registry can route issuers deterministically before structural scoring.

This gate does **not** promote scores or weights. It resolves business-model applicability and records provenance.

## Official source contract

The B3 listed-companies application currently exposes:

- `GetDownloadIndustryClassification` — downloads the official `ClassifSetorial.xlsx` workbook.
- `GetInitialCompanies` — paginated listed-company catalog containing `issuingCompany`, `codeCVM`, CNPJ and listing metadata.

The workbook contains the economic hierarchy:

- economic sector;
- subsector;
- economic segment;
- trading name;
- issuer code;
- listing segment.

Identity is resolved only through official B3 fields:

`workbook issuer code -> catalog issuingCompany -> catalog codeCVM/CNPJ -> cvm:<codeCVM>`

No ticker-name inference or fuzzy company-name matching is used.

## Point-in-time rule

`ClassifSetorial.xlsx` is a **current collection-time snapshot**. The normalized `SectorClassificationRecord` therefore has:

- `snapshot_scope = CURRENT`;
- `point_in_time_eligible = false`.

The snapshot may route a current analysis. It must **not** be reused as if it described an issuer's historical sector in walk-forward or backtests. Historical model routing requires historical classification snapshots or another point-in-time source.

## Bootstrap behavior

Current sector classification is opt-in:

`include_current_sector_classification=False`

When enabled, the bootstrap preserves:

1. raw `ClassifSetorial.xlsx`;
2. raw paginated B3 company-catalog responses inside an auditable ZIP;
3. normalized B3 sector classifications joined to stable CVM company IDs.

The normal annual bootstrap remains historical by default and therefore does not silently ingest the current snapshot.

## Applicability behavior

The coverage profiler can receive the v0.6 `SectorModelRegistry` and records:

- resolved model ID and selection reason;
- whether routing used the default fallback;
- sector/subsector/segment;
- current-snapshot point-in-time eligibility;
- whether the general-corporate accounting contract is applicable or a specialized contract is still required.

Banks and insurers are explicitly marked `SPECIALIZED_ACCOUNTING_CONTRACT_REQUIRED`. Their general-corporate coverage remains diagnostic only and cannot establish rankability.

## Real-data acceptance gate

The bounded official-source smoke test activates the current snapshot and requires deterministic non-fallback routing for the benchmark set:

- PETR4 -> `commodities`;
- VALE3 -> `commodities`;
- ITUB4 -> `banks`.

The smoke also requires every profiled company-year to have a resolved current sector model and verifies that the B3 classification records remain `point_in_time_eligible = false`.
