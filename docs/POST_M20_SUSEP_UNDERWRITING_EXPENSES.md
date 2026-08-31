# Post-M20 SUSEP underwriting expenses

## Verified metric: commercial expense ratio

The official SUSEP market reports distinguish commercial expenses (DC), administrative expenses (DA), earned premium (PG), and incurred/retained claims when discussing insurer underwriting performance. They explicitly present the commercial-expense index as commercial expenses relative to earned premium and define the combined ratio as including claims, commercial expenses, and administrative expenses.

The official SES archive schema already verified in this project exposes the exact raw column `desp_com` together with `premio_ganho` and `sinistro_ocorrido`.

For the current methodology era, beginning with complete fiscal years from FY2014 onward, the project derives:

`commercial_expense_ratio = sum(desp_com) / sum(premio_ganho)`

for one exact numeric SUSEP company identifier and only when all twelve monthly periods are present.

## Fail-closed rules

- exact numeric SUSEP company identifier only;
- all 12 months of the fiscal year are required;
- `premio_ganho`, `sinistro_ocorrido`, and `desp_com` must all be numeric and complete;
- annual earned premium must be strictly positive;
- commercial expenses and incurred claims must not be negative;
- invalid or incomplete evidence produces `None`;
- current SES historical downloads remain `point_in_time_eligible=false`.

## Deliberate scoring boundary

`commercial_expense_ratio` is verified evidence, but it is **not** promoted to the existing generic `expense_ratio` scoring key yet. SUSEP's official combined-ratio methodology also includes administrative expenses. Until the exact SES administrative-expense field and its aggregation contract are independently verified, mapping commercial expenses alone to generic total underwriting expenses would overstate semantic coverage.

Likewise, `combined_ratio` remains `UNKNOWN` until the administrative-expense component is verified. The 65% insurer ranking coverage gate is unchanged.

## Official evidence

- SUSEP, Relatórios de Análise e Acompanhamento dos Mercados Supervisionados: reports distinguish sinistralidade, commercial expenses, administrative expenses, combined ratio, and combined ratio expanded.
- SUSEP historical methodology states `IC = (SR + DC + DA) / PG` and identifies DC as Despesas Comerciais, DA as Despesas Administrativas and PG as Prêmio Ganho.
- From December 2013 onward, SUSEP reports earned premium as gross of reinsurance; the project therefore starts complete-year current-era derivations at FY2014.
