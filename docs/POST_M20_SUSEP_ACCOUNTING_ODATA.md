# Post-M20 — SUSEP accounting OData source contract

## Purpose

SUSEP publishes an official OData service for accounting information of supervised companies. The service exposes separate accounting resources for assets, liabilities, insurer DRE, reinsurer DRE, DMPL, DMPS and cash-flow statements.

The documented row contract includes `entnome`, `cnpj`, `mesreferencia`, `cmpid`, `cmptitulo`, `valor` and `cmpnumero`. This gives the project a machine-readable official source that can be joined deterministically by exact CNPJ and exact CMPID without company-name inference.

## Current scope

This change deliberately establishes the transport/schema contract before using the service for scoring. `SusepAccountingODataService` can:

- inspect the exact entity-set names exposed by the official OData service document;
- parse documented accounting rows into a typed, normalized record;
- normalize CNPJ using the same exact identity rules used by the SUSEP licensed-entity collector;
- preserve accounting values as `Decimal`;
- retry only transient network failures, HTTP 429 and server errors with bounded backoff.

The permanent smoke stores only service metadata and entity-set names. It never persists financial rows.

## Evidence boundary

The accounting API is a latest-state public service. This contract does not establish revision history or publication timestamps for historical rows. Therefore records remain `point_in_time_eligible=false` for strict walk-forward/backtesting until revision-aware/publication-timing evidence exists.

No score-facing metric is promoted by this source-contract change. Existing verified insurer ROE/ROA semantics remain unchanged and the 65% ranking coverage gate remains unchanged.

## Next gate

The exact entity-set names returned by the live service smoke will be used to bind dedicated collectors for the insurer DRE and balance sheet. Only after a real smoke validates exact request shapes and fields may those collectors feed verified metrics such as annual net income and five-year net-income CAGR.
