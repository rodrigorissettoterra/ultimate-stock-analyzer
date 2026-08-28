# M10 — Accounting Quality, Audit, Governance and Insider Alignment

Status: **implemented in v1.0 candidate**.

## Objective

M10 adds evidence-backed quality controls that stay separate from price, valuation and entry timing.

### Accounting Quality Score

The deterministic engine evaluates, when available:

- operating cash flow / net income;
- free cash flow / net income;
- accrual ratio relative to average assets;
- change in receivables relative to revenue;
- change in inventories relative to revenue;
- dependence on non-recurring income.

Missing inputs reduce coverage. They never become zero and are never invented by the LLM.
Weights and anchors are hypotheses pending M15/M16 calibration.

### Audit Risk

Audit observations are explicit sourced events. Critical observations can block a recommendation.
The module can also derive auditor-change events from historical FRE auditor records; frequent
changes are a warning, not automatic evidence of misconduct.

Primary free source: CVM Formulário de Referência (FRE), including its structured independent-
auditor records. FRE also contains management, capital, financial and related-party information.

### Governance

Governance evidence is represented as source-linked facts. v1.0 supports board independence,
audit/fiscal committees, related-party policy, compensation disclosure, tag-along, ownership
concentration and free float. A score is rankable only with sufficient weighted coverage and a
strong share of official evidence.

Primary free sources:

- CVM Informe do Código de Governança (ICBGC), updated weekly;
- CVM Formulário de Referência (FRE);
- B3 issuer/listing information as a cross-check when needed.

### Insider Alignment

Insider transactions are evidence, not an automatic buy/sell signal. The score uses priced
purchase/sale direction and exposes confidence. Unpriced transactions remain visible but do not
receive invented notional values.

Primary free source: CVM Valores Mobiliários Negociados e Detidos (VLMO), periodic disclosure
under Resolução CVM 44 and available as annual ZIP resources.

### Structured CVM ZIP ingestion

`CVMStructuredZipCollector` accepts only HTTPS URLs on `dados.cvm.gov.br`, reads CSV members from
the official ZIPs and preserves raw column names. Semantic field mapping remains explicit and
versioned so a CVM schema change cannot silently change a financial score.

## Public-repository safety

The repository contains parsers, schemas, formulas and synthetic test fixtures only. It does not
redistribute bulk CVM/B3 datasets. Users reconstruct source data from official portals.
