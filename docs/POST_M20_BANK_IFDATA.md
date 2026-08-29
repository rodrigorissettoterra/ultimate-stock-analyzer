# Post-M20 — BCB IFData Bank Accounting Contract

Status: **implemented in the Post-M20 bank evidence gate**.

## Objective

Add a bank-specific accounting evidence layer without applying industrial-company leverage
metrics to banks and without promoting unverified proxies into the `bank_v1` structural model.

The first production contract uses the official, free Banco Central do Brasil IFData OData
service. The normalized unit is the **prudential conglomerate** (`TipoInstituicao=1`).

## Identity contract

The CVM issuer remains the master company identity (`company_id=cvm:<CD_CVM>`).

A bank issuer is linked to IFData only when:

1. the first eight digits of the CVM issuer CNPJ match IFData `CnpjInstituicaoLider`;
2. the IFData row is active (`Situacao=A`);
3. `CodInst == CodConglomeradoPrudencial`.

No issuer-name or ticker fuzzy match is allowed. Ambiguous matches fail closed.

For Itaú in the 2025 annual smoke, this resolves to prudential conglomerate `C0080099`
(`ITAU - PRUDENCIAL`) with leader CNPJ root `60872504`.

## Official reports used

The first contract reads only verified IFData reports and accounts:

- Report 1 — `Resumo`
  - `140220`: Ativo Total
  - `140246`: Patrimônio Líquido
  - `141873`: Carteira de Crédito
- Report 4 — `Demonstração de Resultado`
  - `141870`: Lucro Líquido
  - `141840`: Resultado com Perda Esperada de Operações de Crédito
- Report 5 — `Informações de Capital`
  - `79659`: Índice de Capital Principal
  - `79660`: Índice de Capital Nível I
  - `79661`: Razão de Alavancagem
  - `79664`: Índice de Basileia

The production collector intentionally does not use an OData `$filter` on `CodInst`.
The current service returned an incompatible-type error for that expression during contract
discovery. Instead, the selected report is downloaded and the exact `CodInst` is filtered
locally.

## Income-statement periodicity

BCB accounting rules and the live IFData data both show that:

- March and September carry quarterly income-statement results;
- June and December carry semester results.

Therefore an annual flow is calculated as:

```text
annual_flow = June_semester + December_semester
```

The code does **not** sum all four reference dates and does **not** treat December as YTD.

## Deterministic metrics enabled

The first verified bank profile derives:

- `roe = annual_net_income / average(prior_equity, current_equity)`
- `roa = annual_net_income / average(prior_assets, current_assets)`
- `cost_of_credit = -annual_credit_loss_result / average(prior_credit, current_credit)`
- `equity_to_assets = current_equity / current_assets`

and carries the official:

- `basel_ratio`
- `tier1_ratio`
- `core_equity_tier1_ratio`
- `leverage_ratio`.

The denominator helper fails to `UNKNOWN` when a required balance is missing or non-positive.

## Metrics deliberately left UNKNOWN

This implementation does **not** manufacture the following `bank_v1` inputs:

- `net_interest_margin`
- `npl_90d_ratio`
- `npl_coverage`
- `efficiency_ratio`
- `fee_income_share`
- five-year loan and net-income growth.

Reports 11 and 13 expose credit overdue from **15 days**, not 90 days. They are therefore not
renamed or used as a proxy for `npl_90d_ratio`.

The bank must remain non-rankable when the specialized structural evidence is below the normal
coverage/confidence gates.

## Point-in-time safety

IFData publishes quarterly information with a known reporting delay, so the annual profile
stores a conservative `available_from_estimate` of April 1 following the fiscal year.

However, the public historical API returns the latest state of a historical row and does not
provide the revision history required to reproduce exactly what was visible on a past date.
Consequently:

```text
point_in_time_eligible = false
```

for these normalized historical bank profiles.

The profile is valid for current/research evidence and coverage diagnostics, but strict
walk-forward backtests must not consume it until revision-aware snapshots are available.

## Bootstrap artifacts

When `include_bank_ifdata=True`, the public bootstrap preserves:

- exact raw IFData cadastro/report JSON payloads;
- normalized annual prudential profiles;
- SHA-256, byte size and row counts in the normal bootstrap manifest.

No paid source, investment weight, recommendation, or LLM-calculated financial metric is
introduced by this contract.

## Official references

- BCB IFData open dataset:
  `https://dadosabertos.bcb.gov.br/dataset/ifdata---dados-selecionados-de-instituies-financeiras`
- BCB IFData OData:
  `https://olinda.bcb.gov.br/olinda/servico/IFDATA/versao/v1/odata`
