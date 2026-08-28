# Data Sources Registry

The project follows this priority: **official free source → public free source → own derivation → open-source adapter → paid source only when no adequate free alternative exists**.

| Domain | Primary free source | Use | Redistribution policy |
|---|---|---|---|
| Financial statements | CVM Open Data | DFP/ITR structured statements | Store locally; publish collectors/schemas, not bulk mirrors |
| Company reference / governance | CVM FRE + governance datasets | ownership, administration, risks, governance | Same principle |
| Securities / market events | B3 public data | tickers, corporate events, historical market data | Follow B3 terms; do not bulk mirror in Git |
| Securities lending | B3 public data | registered loans, historical operations, rates | Follow B3 terms; local processing only |
| Macro | Banco Central SGS | Selic, FX, credit and related series | Retrieve from source programmatically |
| Macro / economic activity | IBGE / IpeaData | inflation, GDP, labor and other series | Retrieve from source programmatically |
| Fundamental cross-check | Fundamentus / `fundamentus` library | prototype/cross-check only | Not source of truth |
| Company documents | issuer IR + CVM/B3 | releases, guidance, material facts | Store metadata/derived features; avoid republishing protected content |
| News | open/public financial sources | event detection and classification | Store metadata, short snippets if permitted, and derived features |
| Analyst consensus | free sources if adequate | future estimates/revisions | Paid provider may be considered only after demonstrated need |

## Paid-resource gate

A paid resource is allowed only when all conditions are met:

1. The variable is materially useful to the model.
2. No adequate official/public free source exists.
3. It cannot be reasonably derived from existing data.
4. Its absence materially harms model quality.
5. Its incremental value can be tested or otherwise justified.
6. Cost, terms and licensing are explicitly approved before adoption.
