# Post-M20 — contrato especializado de seguradoras / SUSEP

## Objetivo

Iniciar o contrato especializado de seguradoras sem reutilizar automaticamente o
modelo contábil corporativo genérico. A fonte regulatória primária é a SUSEP.

Este bloco cria somente a fundação verificável do contrato. Nenhum indicador
estrutural de seguradoras é considerado preenchido enquanto o mapeamento exato de
campos e a fórmula regulatória correspondente não forem comprovados.

## Fonte oficial

A base pública escolhida é o **SES — Sistema de Estatísticas da SUSEP**.

A própria SUSEP informa que:

- os dados do SES vêm dos Formulários de Informações Periódicas (FIP) enviados pelas
  companhias supervisionadas;
- a base completa e as consultas on-line são atualizadas semanalmente;
- dados históricos podem sofrer alteração por recargas após análises da SUSEP;
- o SES fornece informações sobre operações totais das empresas, operações por
  mercado e produtos.

O Plano de Dados Abertos 2025–2026 da SUSEP identifica o SES/BDESTATIST como a
principal base pública da autarquia e esclarece que o SES publica a parcela do
SAPIEMS que pode ser disponibilizada ao público.

## Contrato temporal

Como a SUSEP declara que valores históricos podem ser alterados por recargas e o
download corrente não expõe, no contrato que verificamos, um histórico reproduzível
de versões/revisões, a base é classificada inicialmente como:

```text
revision_aware = false
point_in_time_eligible = false
```

Isso impede o uso silencioso desses valores em backtests PIT estritos.

## Identidade

A identidade de uma seguradora deve ser resolvida por identificadores oficiais.

Regras do contrato:

1. partir da identidade CVM estável (`company_id = cvm:<CD_CVM>`);
2. usar CNPJ/registro oficial da entidade licenciada pela SUSEP para estabelecer a
   correspondência com o código da companhia na SUSEP;
3. não usar ticker, similaridade de nome ou fuzzy matching como autoridade de join;
4. manter a correspondência ausente como `UNKNOWN` quando o identificador oficial
   não puder ser comprovado.

A SUSEP mantém serviço oficial de consulta de entidades licenciadas e informa que a
consulta contém informações básicas das supervisionadas autorizadas.

## Tabelas candidatas

A documentação pública do ecossistema SES confirma a existência, entre outras, das
seguintes tabelas relevantes para o modelo:

- `Ses_cias.csv` — cadastro de companhias;
- `Ses_seguros.csv` — prêmios e sinistros;
- `Ses_pl_margem.csv` — patrimônio líquido / margem de solvência;
- `Ses_seg_prov_det.csv` — provisões detalhadas;
- `ses_provramos.csv` — provisões por ramo.

Os nomes são registrados aqui como **candidatos de origem**, não como autorização
para inferir campos. O mapeamento de colunas será aceito somente quando confrontado
com a documentação da tabela/FIP e uma amostra oficial real.

## Métricas previstas no modelo `insurance_v1`

O arquivo `insurance_v0.6.yml` já reserva indicadores para:

- rentabilidade: `roe`, `roa`;
- qualidade de subscrição: `combined_ratio`, `loss_ratio`, `expense_ratio`;
- capital: `solvency_ratio`, `capital_adequacy_ratio`,
  `technical_provisions_coverage`;
- crescimento e previsibilidade em cinco anos;
- dividendos.

Neste estágio, todos esses campos continuam `UNKNOWN`.

## Prudencial

A regulação prudencial da SUSEP utiliza conceitos formais como Patrimônio Líquido
Ajustado (PLA), Capital Mínimo Requerido (CMR), provisões técnicas e cobertura das
provisões. O serviço oficial de certidões descreve a suficiência de capital como a
situação em que `PLA >= CMR`.

Isso torna `PLA` e `CMR` candidatos fortes para uma futura métrica de solvência, mas
**não** autoriza neste bloco a assumir que `solvency_ratio = PLA / CMR`. Essa fórmula
só será ativada após confirmação explícita de que ela corresponde à semântica
pretendida pelo modelo.

## Implementação

Foi adicionado `InsuranceSusepAnnualRecord` ao domínio, com os campos brutos e
métricas especializadas opcionais. Todos começam como `None`.

O módulo `ultimate_stock_analyzer.collectors.susep_ses` registra o contrato da fonte:

- fonte oficial pública;
- atualização semanal;
- sem revisão histórica comprovada;
- `point_in_time_eligible = false`;
- registro oficial de entidade requerido para identidade;
- fuzzy matching proibido.

O próximo bloco deve materializar a ingestão da base oficial, verificar o esquema real
das tabelas e promover métricas uma a uma, preservando a política fail-closed.
