# Post-M20 — razão de solvência SUSEP

## Métrica promovida

O modelo especializado de seguradoras passa a aceitar `solvency_ratio` a partir da
comparação prudencial oficial entre Patrimônio Líquido Ajustado (PLA) e Capital Mínimo
Requerido (CMR):

```text
solvency_ratio = PLA / CMR
```

A SUSEP descreve o principal indicador de solvência como uma comparação entre PLA e
CMR e exige suficiência de PLA frente ao CMR. Demonstrações contábeis supervisionadas
publicadas pela própria SUSEP apresentam a suficiência de capital como `PLA - CMR` e o
percentual de suficiência como `(PLA - CMR) / CMR`. Portanto, `PLA / CMR` representa
diretamente a cobertura do requisito: 1,0 é o limiar de suficiência; abaixo de 1,0 há
insuficiência.

## Fonte e período

A origem é `Ses_pl_margem.csv`, cuja existência e esquema são monitorados pelo smoke
permanente da base oficial `BaseCompleta.zip`.

Campos utilizados:

- `coenti` — código oficial da supervisionada;
- `damesano` — período de referência;
- `plajustado` — PLA;
- `CMR` — Capital Mínimo Requerido.

Para uma observação estrutural anual usa-se exclusivamente o snapshot de dezembro
(`YYYY12`), sem somar valores mensais.

## Regras fail-closed

A métrica permanece `UNKNOWN` quando:

- não existe exatamente uma linha para a companhia e `YYYY12`;
- qualquer valor requerido é ausente ou não numérico;
- PLA é negativo;
- CMR é zero ou negativo;
- a identidade não é um código SUSEP numérico oficial.

Não há fuzzy matching, interpolação ou preenchimento por LLM.

## Limitação temporal

O download corrente do SES pode conter recargas históricas e não oferece contrato de
revisões reproduzível. Por isso:

```text
point_in_time_eligible = false
```

A métrica pode alimentar o score estrutural corrente, mas não um backtest PIT estrito
até que uma fonte revision-aware/publication-aware seja comprovada.

## Cobertura do modelo

No `insurance_v0.6.yml`, `solvency_ratio` vale 45% da categoria `capital`, que vale
20% do score estrutural. Portanto, esta métrica pode contribuir com até 9 pontos
percentuais de cobertura. O gate de ranking de 65% permanece inalterado.

`capital_adequacy_ratio` e `technical_provisions_coverage` continuam `UNKNOWN` até
terem contratos independentes verificados; não são inferidos a partir de PLA/CMR para
inflar cobertura.
