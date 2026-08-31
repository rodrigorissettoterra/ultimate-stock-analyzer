# SUSEP profitability field evidence gate

This gate verifies current official `Ses_campos.csv` dictionary rows relevant to insurer profitability before any score-facing ROE/ROA mapping is allowed.

The permanent SUSEP schema smoke performs two conservative checks:

1. exact candidate CMPIDs `518`, `1039`, `3333`, and `5035`;
2. fixed literal descriptions after case/accent normalization:
   - `ATIVO TOTAL`
   - `TOTAL DO ATIVO`
   - `PATRIMONIO LIQUIDO`
   - `LUCRO LIQUIDO`
   - `RESULTADO LIQUIDO`
   - `RESULTADO DO EXERCICIO`

The candidate IDs have regulator-document provenance: SUSEP's insurer economic-financial methodology identifies `518` as net income, `1039` as total assets, and `3333` as equity in the profitability formula; separate prudential material documents `5035` as equity in the Q28/PLA context. The live dictionary smoke is still required because the current SES archive is the operational source contract.

The manifest contains dictionary metadata only (`nuitem`, `noitem`, `nuquad`, `mercado`, validity dates). It never persists supervised-company financial values.

A dictionary match is evidence for review, not automatic semantic promotion. ROE/ROA may enter insurer scoring only when the live dictionary confirms the expected IDs/descriptions, relevant market/accounting frame and validity interval. Profit-and-loss annualization and balance-sheet snapshot semantics must also be explicit in the calculation contract.

Current SUSEP historical downloads remain revision-prone and therefore `point_in_time_eligible=false` for strict PIT backtests.
