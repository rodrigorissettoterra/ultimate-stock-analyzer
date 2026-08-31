# Post-M20 — SUSEP issuer/entity identity contract

## Purpose

Listed-company scoring must never connect a CVM/B3 issuer to SUSEP data by ticker, company name, substring, or fuzzy similarity. SUSEP publishes supervised-entity identity data with both CNPJ and Código FIP, which provides the deterministic bridge required by the project.

## Official machine-readable source

SUSEP's `Dados Cadastrais das Entidades - v1` service is an official OData API. Its documented `Dados Cadastrais` resource exposes:

- `mercodigo` — regulated-market code;
- `entcodigofip` — Código FIP assigned by SUSEP;
- `entnome` — legal name;
- `entcgc` — entity CNPJ.

Canonical resource:

`https://dados.susep.gov.br/olinda/servico/empresas/versao/v1/odata/DadosCadastrais`

`SusepOlindaIdentityCollector` requests only those identity fields, pages deterministically by Código FIP and validates every row before it becomes identity evidence. It does not query by company name or ticker.

## Matching contract

The implementation normalizes issuer CNPJ to exactly 14 digits and matches only records whose official CNPJ is identical. Código FIP is treated as a digit string and leading zeroes are preserved.

A match returns every distinct `(CNPJ, Código FIP)` pair. This is deliberate: the broader insurer model must not assume that a listed insurance group is always represented by a single supervised legal entity. Any future aggregation across several supervised entities must be supported by separately verified ownership/group evidence and must aggregate financial numerators and denominators before ratios are calculated.

Names remain evidence/display metadata only. They are never identity keys.

## Fail-closed rules

- malformed CNPJ -> error;
- malformed Código FIP -> error;
- malformed OData response/identity row -> error;
- no exact CNPJ match -> no supervised entity returned;
- similar legal/trade name -> ignored unless CNPJ matches exactly;
- duplicate registry rows for the same CNPJ/FIP pair -> de-duplicated deterministically;
- pagination exceeding the configured safety bound -> error;
- no ticker-based, name-based or fuzzy fallback.

## Scope boundary

The Olinda API establishes exact identity of individual supervised legal entities. It does not by itself establish that a listed holding company owns every supervised entity in a group. A future issuer-to-entity-set relationship must therefore use independently verified corporate/ownership evidence rather than name proximity.

This identity contract does not alter the point-in-time status of SES financial data. Current SUSEP historical downloads remain revision-prone and `point_in_time_eligible=false` for strict historical backtests.
