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

Os seguintes nomes foram identificados como **candidatos de origem** para inspeção da
base completa do SES:

- `Ses_cias.csv` — cadastro de companhias;
- `Ses_seguros.csv` — prêmios e sinistros;
- `Ses_pl_margem.csv` — patrimônio líquido / margem de solvência;
- `Ses_seg_prov_det.csv` — provisões detalhadas;
- `ses_provramos.csv` — provisões por ramo.

Eles não são tratados pelo código como tabelas verificadas. A existência de cada
arquivo, seu esquema e sua semântica devem ser comprovados no arquivo oficial
`BaseCompleta.zip` e confrontados com a documentação oficial antes de qualquer campo
ser promovido a métrica do modelo.

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

## Ingestão segura do arquivo oficial

`SusepSesCollector` fornece agora a camada mínima para trabalhar com a base oficial sem
inferir semântica:

- baixa `BaseCompleta.zip` diretamente da URL oficial;
- lista somente CSVs realmente presentes no ZIP;
- resolve uma tabela por **nome de arquivo exato**, com comparação apenas
  case-insensitive;
- falha se a tabela estiver ausente ou se houver mais de uma correspondência;
- lê o CSV preservando os nomes brutos das colunas;
- permite inspecionar o esquema oficial sem transformá-lo em métricas.

Não há fuzzy matching de tabelas, inferência de campos nem valores calculados por LLM.
Os dados baixados continuam fora do Git.

## Implementação

`InsuranceSusepAnnualRecord` permanece com campos brutos e métricas especializadas
opcionais. Todos os indicadores ainda não comprovados continuam `None`.

O módulo `ultimate_stock_analyzer.collectors.susep_ses` registra e aplica o contrato:

- fonte oficial pública;
- atualização semanal;
- sem revisão histórica comprovada;
- `point_in_time_eligible = false`;
- registro oficial de entidade requerido para identidade;
- fuzzy matching proibido;
- nomes de tabelas mantidos explicitamente como candidatos, não como verificados.

O próximo bloco deve executar a inspeção contra o `BaseCompleta.zip` real, registrar o
esquema observado e então promover métricas uma a uma somente com evidência oficial.
