# Post-M20 — primeira métrica verificada de seguradoras: loss ratio

## Escopo

Este bloco promove somente `loss_ratio` para o contrato especializado `insurance_v1`.
As demais métricas de seguradoras continuam `UNKNOWN` até terem campos e fórmulas
oficiais comprovados de forma independente.

## Evidência oficial

A inspeção real do `BaseCompleta.zip` da SUSEP confirmou `Ses_seguros.csv` com os
campos `damesano`, `coenti`, `cogrupo`, `coramo`, `premio_ganho`, `sinistro_ocorrido`
e `desp_com`.

A documentação oficial de tabelas identifica `premio_ganho` como **Prêmio Ganho
(R$)**. O glossário oficial do SES define Prêmio Ganho e Sinistros Ocorridos como
valores brutos de resseguro:

- https://www2.susep.gov.br/menuestatistica/descricao.htm

O Relatório de Análise e Acompanhamento dos Mercados Supervisionados da SUSEP registra
que, a partir de dezembro de 2013, o prêmio ganho passou a ser bruto de resseguro e a
sinistralidade passou a ser medida pelo sinistro ocorrido. Para evitar um exercício
anual com conceitos misturados, o contrato implementado começa em FY2014:

- https://www.gov.br/susep/pt-br/arquivos/arquivos-dados-estatisticos/relatorios-de-analise-e-acompanhamento-dos-mercados-supervisonados/relat_acomp_mercado_2023.pdf/@@display-file/file

## Fórmula

Para uma companhia SUSEP e um exercício completo:

```text
annual_earned_premiums = sum(premio_ganho)
annual_incurred_claims = sum(sinistro_ocorrido)
loss_ratio = annual_incurred_claims / annual_earned_premiums
```

A agregação usa somente linhas cujo `coenti` corresponde exatamente ao identificador
numérico oficial e cujo `damesano` pertence ao exercício solicitado.

## Gate de completude

A métrica só é produzida quando os 12 meses (`YYYY01` a `YYYY12`) estão presentes.
Qualquer mês ausente, valor não numérico, prêmio ganho anual não positivo ou sinistro
anual negativo faz a métrica falhar fechada para `None`.

O código não usa ticker, similaridade de nome, fuzzy matching, interpolação ou LLM
para preencher identificadores ou valores.

## Limite temporal / PIT

O SES corrente pode alterar valores históricos por recargas e não oferece, no
contrato verificado, histórico reproduzível de revisões. Portanto:

```text
point_in_time_eligible = false
source = SUSEP_SES_DERIVED
```

A métrica pode alimentar o score estrutural corrente, mas não pode ser usada como se
fosse evidência point-in-time em backtests históricos estritos.

## Cobertura do modelo

Em `insurance_v0.6.yml`, a categoria `underwriting_quality` pesa 30% e `loss_ratio`
pesa 30% dentro da categoria. Assim, esta promoção adiciona até **9 pontos
percentuais de cobertura estrutural** quando a observação é válida. O gate global de
65% não é reduzido.
