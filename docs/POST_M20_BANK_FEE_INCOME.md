# Post-M20 bank service-income share evidence

## Scope

This increment adds `fee_income_share` to the specialized bank scoring evidence path for fiscal periods covered by the 2025+ COSIF/IFData report-4 layout. The metric is implemented as the Banco Central-style participation of service income in an operating-revenue approximation. It does not change the bank rankability threshold, source hierarchy, identity rules, or point-in-time policy.

## Official methodological basis

The Banco Central's *Relatório de Economia Bancária 2018* studies the participation of financial-service revenue in operating revenue and states that, for that study, operating revenue is approximated by the sum of financial-service revenue and financial-intermediation revenue.

The 2022 and 2023 editions of the *Relatório de Economia Bancária* show the composition of bank service income and explicitly include the result from payment transactions among service-income components.

The Cosif revenue rules classify service revenue under the operational-revenue group and define the service-revenue account family used by regulated institutions.

## 2025+ IFData evidence contract

The exact prudential-conglomerate report-4 rows verified in the official 2025-12 payload for `C0080099` are used by identifier only.

Service-income components:

- `141856` — Rendas de Tarifas Bancárias `(m)`;
- `141857` — Outras Rendas de Prestação de Serviços `(n)`;
- `141855` — Resultado com Transações de Pagamento `(l)`.

Financial-intermediation income components before expected-loss and funding-expense lines:

- `141825` — Rendas de Aplicações Interfinanceiras de Liquidez `(a)`;
- `141830` — Rendas de Títulos e Valores Mobiliários `(b)`;
- `141835` — Rendas de Operações de Crédito `(c)`;
- `141836` — Rendas de Arrendamento Financeiro `(d)`;
- `141837` — Rendas de Outras Operações com Características de Concessão de Crédito `(e)`.

Names are documentary evidence only. Production selection remains exact-account-ID based and does not use fuzzy semantic matching.

## Annual reconstruction

IFData DRE flows remain annualized as June semester + December semester.

```text
service_income_half = m + n + l
financial_intermediation_income_half = a + b + c + d + e

annual_service_income = Jun_service_income + Dec_service_income
annual_financial_intermediation_income =
    Jun_financial_intermediation_income + Dec_financial_intermediation_income

operating_revenue_proxy =
    annual_service_income + annual_financial_intermediation_income

fee_income_share = annual_service_income / operating_revenue_proxy
```

Every component is required. If a required row is absent or the resulting operating-revenue proxy is non-positive, `fee_income_share` remains `UNKNOWN` (`None`).

## Semantic note

The configuration key remains `fee_income_share` for compatibility with `bank_v1`, but the evidence contract is broader than bank tariffs alone: it follows the BCB service-income concept used in the REB methodology and therefore includes the net result from payment transactions. The system does not relabel this as a statutory accounting total of all Cosif operational revenues.

## Historical boundary

The report-4 structure changed at the 2025 COSIF transition. This increment does not infer a legacy mapping from labels or third-party tables. Pre-2025 `fee_income_share` remains `UNKNOWN` until the old-layout account contract is independently verified against official payload evidence.

## Point-in-time treatment

The IFData API exposes latest-state historical observations without a revision timeline. The bank profile therefore continues to use `point_in_time_eligible=false` for strict historical backtests.

## Structural coverage

Under `banks_v0.6`, `fee_income_share` contributes 30% of the 15% efficiency category, or 4.5 percentage points. Together with the previously verified 55.5% subset, the verified structural coverage reaches 60.0%.

The rankability gate remains unchanged at 65%, so the bank model still abstains from ranking when only the currently verified bank-specific metrics are present.

## Sources

- Banco Central do Brasil, *Relatório de Economia Bancária 2018*, competition study and operating-revenue approximation.
- Banco Central do Brasil, *Relatório de Economia Bancária 2022* and *2023*, composition of service income.
- Banco Central do Brasil, Cosif operational/service revenue rules.
- Banco Central do Brasil, official IFData report-4 prudential-conglomerate payload, 2025-12.
