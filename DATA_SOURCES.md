# Data Sources Registry

The project follows this priority: **official free source → public free source → own derivation → open-source adapter → paid source only when no adequate free alternative exists**.

| Domain | Primary free source | Use | Redistribution policy |
|---|---|---|---|
| Issuer registry | CVM `cad_cia_aberta.csv` | stable CVM code, CNPJ, legal name, registration status | Retrieve programmatically; no bulk mirror in Git |
| Security master | CVM FCA | security type, trading code, market and document history | Store locally; publish collectors/schemas only |
| Financial statements | CVM Open Data | DFP/ITR structured statements and restatements | Store locally; publish collectors/schemas, not bulk mirrors |
| Company reference / governance | CVM FRE + governance datasets | ownership, administration, risks, governance | Same principle |
| Bank prudential / credit metrics | BCB IFData | Basel/Tier 1 context, credit quality, institution/conglomerate data and bank-specific reports | Query official API/OData/JSON; keep local derived data, no bulk mirror |
| Insurance market / financial metrics | SUSEP open data + supervised-company financial statements | premiums, claims, provisions, underwriting/solvency context | Retrieve from official sources; publish collectors/schemas and derived features only |
| Securities / market events | B3 public data | corporate events and historical market data | Follow B3 terms; do not bulk mirror in Git |
| Securities lending | B3 public data | registered loans, historical operations, rates | Follow B3 terms; local processing only |
| Macro | Banco Central SGS | Selic, FX, credit and related series | Retrieve from source programmatically |
| Macro / economic activity | IBGE / IpeaData | inflation, GDP, labor and other series | Retrieve from source programmatically |
| Fundamental cross-check | Fundamentus / `fundamentus` library | prototype/cross-check only | Not source of truth |
| Company documents | issuer IR + CVM/B3 | releases, guidance, material facts | Store metadata/derived features; avoid republishing protected content |
| News | open/public financial sources | event detection and classification | Store metadata, short snippets if permitted, and derived features |
| Analyst consensus | free sources if adequate | future estimates/revisions | Paid provider may be considered only after demonstrated need |

## Sector-source notes

### Banco Central IFData

IFData is an official BCB open-data dataset with API/OData/JSON access. It is quarterly, starts
in March 2000, and is sourced from SCR and COSIF. The BCB states that March/June/September
reports are normally published 60 days after quarter-end and December reports 90 days after
year-end. The agent must preserve that availability lag in point-in-time backtests.

### SUSEP

SUSEP maintains an open-data program, market-statistics panels and supervised-company financial
statements. Insurance-specific metrics must retain the original reference period and publication
or collection timestamp. If a metric cannot be reproduced from an official/public source, it
remains missing rather than being inferred by the LLM.

## Current CVM cadence

The company registry is updated daily. FCA, DFP and ITR structured archives are updated
periodically by the CVM and may include re-presentations. The ingestion layer retains CVM
document ids, versions and receipt timestamps instead of overwriting history.

## Paid-resource gate

A paid resource is allowed only when all conditions are met:

1. The variable is materially useful to the model.
2. No adequate official/public free source exists.
3. It cannot be reasonably derived from existing data.
4. Its absence materially harms model quality.
5. Its incremental value can be tested or otherwise justified.
6. Cost, terms and licensing are explicitly approved before adoption.
