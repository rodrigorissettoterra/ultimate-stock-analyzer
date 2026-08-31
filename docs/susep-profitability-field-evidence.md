# SUSEP profitability field evidence gate

This gate discovers official `Ses_campos.csv` dictionary rows relevant to insurer profitability before any score-facing ROE/ROA mapping is allowed.

The permanent SUSEP schema smoke searches only fixed literal descriptions after case/accent normalization:

- `ATIVO TOTAL`
- `LUCRO LIQUIDO`
- `RESULTADO DO EXERCICIO`

The manifest contains dictionary metadata only (`nuitem`, `noitem`, `nuquad`, `mercado`, validity dates). It never persists supervised-company financial values.

A dictionary match is evidence for review, not automatic semantic promotion. A field may enter insurer scoring only after its official description, accounting frame, validity interval, annualization/snapshot semantics, and sign convention are independently validated.

Current SUSEP historical downloads remain revision-prone and therefore `point_in_time_eligible=false` for strict PIT backtests.
