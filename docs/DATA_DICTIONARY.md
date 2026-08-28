# Data Dictionary v0.2

## Canonical issuer

| Field | Meaning |
|---|---|
| company_id | stable internal issuer key (`cvm:<CD_CVM>`) |
| cvm_code | numeric CVM issuer code |
| cnpj | issuer CNPJ when available |
| legal_name | registered legal name |
| trade_name | commercial name when available |
| registration_status | CVM registration status |
| registration_date | CVM registration date |
| cancellation_date | registration cancellation date, if any |
| collected_at | ingestion timestamp |
| source | source authority |

## Canonical security

| Field | Meaning |
|---|---|
| company_id | issuer foreign key |
| ticker | trading code; attribute of the security, never the issuer identity |
| isin | ISIN when available |
| security_type | ordinary/preferred share, unit, BDR, etc. |
| market | trading market |
| administrator | market administrator when reported |
| trading_start / trading_end | admitted trading interval |
| reference_date | FCA reference date |
| version | FCA version |
| available_from | first evidenced public availability timestamp |
| source_document | original FCA CSV |

## Financial statement line

| Field | Meaning |
|---|---|
| company_id | stable issuer key |
| cvm_code / cnpj | external issuer identifiers |
| document_type | DFP or ITR |
| statement | BPA, BPP, DRE, DFC, DRA, DMPL, DVA, etc. |
| consolidation_scope | consolidated/individual group reported by CVM |
| reference_date | statement reference date |
| period_start / period_end | accounting interval represented |
| fiscal_order | current/prior exercise ordering from source |
| account_code / account_name | CVM accounting line identity |
| value_brl | normalized numeric value in BRL |
| source_scale | original CVM currency scale |
| version | CVM document version |
| document_id | CVM document id |
| received_at | CVM receipt timestamp |
| available_from | earliest timestamp usable by point-in-time models |
| collected_at | ingestion timestamp |
| source_document | source CSV filename |

Unknown values are never replaced with invented estimates. Derived values must retain lineage to
their input observations and formula/model version. Point-in-time analysis must not use rows whose
`available_from` is unknown.
