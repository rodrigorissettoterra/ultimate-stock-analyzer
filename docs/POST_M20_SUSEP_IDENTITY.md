# Post-M20 — SUSEP issuer/entity identity contract

## Purpose

Listed-company scoring must never connect a CVM/B3 issuer to SUSEP data by ticker, company name, substring, or fuzzy similarity. SUSEP publishes supervised-entity identity data with both CNPJ and Código FIP, which provides the deterministic bridge required by the project.

## Official machine-readable source

SUSEP's `Dados Cadastrais das Entidades - v1` service is an official OData API. Its documented `Dados Cadastrais` resource exposes `mercodigo`, `entcodigofip`, `entnome` and `entcgc` (regulated-market code, Código FIP, legal name and CNPJ).

Canonical resource:

`https://dados.susep.gov.br/olinda/servico/empresas/versao/v1/odata/DadosCadastrais`

The regulator/Open Insurance documentation references the complete resource using `$format=json`. A real GitHub Actions smoke showed that an attempted richer `$select/$orderby/$skip/$top` request returned HTTP 400, so the collector deliberately uses the verified full-resource request shape instead of assuming optional OData combinations are operational. Exact CNPJ matching is performed locally after validation of every returned identity row.

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
- no ticker-based, name-based or fuzzy fallback.

## Monitoring

The dedicated `susep-identity-smoke` workflow calls the official API and uploads only an aggregate manifest containing counts, expected field names, matching policy and source metadata. Raw registry rows are not committed or uploaded as artifacts.

## Scope boundary

The Olinda API establishes exact identity of individual supervised legal entities. It does not by itself establish that a listed holding company owns every supervised entity in a group. A future issuer-to-entity-set relationship must therefore use independently verified corporate/ownership evidence rather than name proximity.

This identity contract does not alter the point-in-time status of SES financial data. Current SUSEP historical downloads remain revision-prone and `point_in_time_eligible=false` for strict historical backtests.
