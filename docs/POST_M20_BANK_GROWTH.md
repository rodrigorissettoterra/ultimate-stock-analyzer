# Post-M20 — crescimento bancário de 5 anos

## Objetivo

Adicionar uma camada determinística e auditável para os dois indicadores de crescimento já previstos no modelo estrutural de bancos:

- `loan_cagr_5y`;
- `net_income_cagr_5y`.

Os indicadores são derivados exclusivamente dos perfis anuais normalizados do BCB IFData já produzidos pelo bootstrap público. Nenhum campo é inferido por LLM e nenhuma ausência é preenchida artificialmente.

## Convenção temporal

`5y CAGR` significa uma distância de exatamente cinco exercícios fiscais entre os pontos inicial e final. Para FY2025, por exemplo, os endpoints são FY2020 e FY2025 e o expoente é `1/5`.

O contrato exige seis perfis anuais consecutivos: `Y-5`, `Y-4`, `Y-3`, `Y-2`, `Y-1` e `Y`. Essa exigência é mais restritiva do que a matemática do CAGR, mas impede que um histórico esparso seja tratado silenciosamente como evidência longitudinal completa.

## Fórmulas

Para valores inicial e final estritamente positivos:

```text
CAGR_5y = (valor_final / valor_inicial) ** (1 / 5) - 1
```

`loan_cagr_5y` usa `gross_credit_portfolio`.

`net_income_cagr_5y` usa `annual_net_income`.

## Fail closed

O indicador correspondente permanece `UNKNOWN` (`None`) quando:

- qualquer um dos seis exercícios necessários está ausente;
- o campo anual necessário está ausente em algum exercício;
- o endpoint inicial ou final é zero ou negativo;
- um endpoint não é finito;
- o código do conglomerado prudencial (`ifdata_cod_inst`) muda dentro da janela de seis anos.

Não é usado CAGR com sinal, valor absoluto, interpolação ou preenchimento de lacunas.

Uma mudança de conglomerado é tratada como quebra de comparabilidade. Mesmo que a identidade CVM da companhia permaneça estável, o crescimento não é calculado automaticamente através dessa fronteira.

## Point-in-time

Os perfis históricos do IFData disponíveis no contrato atual representam o estado mais recente exposto pela API e não oferecem histórico de revisões comprovado. Consequentemente:

```text
point_in_time_eligible = false
```

Os CAGRs derivados herdam essa restrição e não podem ser usados como evidência em backtests PIT estritos até que uma fonte/revisão historicamente reproduzível seja comprovada.

## Cobertura do modelo bancário

O arquivo `banks_v0.6.yml` reserva 5% do score estrutural à categoria `growth`:

- `net_income_cagr_5y`: 60% da categoria = 3 pontos percentuais;
- `loan_cagr_5y`: 40% da categoria = 2 pontos percentuais.

Com os indicadores oficiais já verificados antes deste bloco, a cobertura disponível era 60%. Quando os dois CAGRs são válidos, a cobertura chega a 65%, exatamente o `min_coverage_for_ranking` atual.

Isso remove apenas o veto específico de baixa cobertura. Não significa, isoladamente, que uma ação bancária será rankeável: continuam valendo confiança mínima, tamanho do peer group, demais flags e todos os gates do motor estrutural.

Também não constitui validação empírica dos pesos. Calibração e promoção de pesos continuam dependentes de backtest histórico e walk-forward fora da amostra.

## Implementação

O módulo `ultimate_stock_analyzer.scoring.bank_growth` fornece:

- `BankGrowthMetrics`;
- `derive_bank_growth_metrics(...)`;
- `bank_growth_features(...)` para produzir nomes compatíveis com o motor de scoring.

A implementação opera sobre `BankPrudentialAnnualRecord`, portanto reutiliza a normalização e a identidade já verificadas no contrato IFData em vez de criar uma segunda interpretação das contas do BCB.
