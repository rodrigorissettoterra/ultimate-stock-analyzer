# Post-M20 CVM IPE Corporate-Action Ledger Audit

## Decision

The official CVM IPE annual archives are useful as a historical, issuer-level document ledger. They do
not replace a structured corporate-action history and do not remove
`PRICE_SERIES_UNADJUSTED_FOR_CORPORATE_ACTIONS`.

This block is diagnostic only. It does not change prices, returns, scores, routing, eligibility,
portfolio behavior, historical readiness or walk-forward readiness.

## Why this source was evaluated

The public B3 `GetListedSupplementCompany` endpoint supplies current observed corporate-action rows,
but its public contract does not prove that every historical row and revision needed for a backtest is
retained. The preceding event-aware coverage audit therefore kept
`B3_SUPPLEMENT_HISTORICAL_COMPLETENESS_UNPROVEN`.

The [CVM IPE dataset](https://dados.cvm.gov.br/dataset/cia_aberta-doc-ipe) publishes annual indexes of
periodic and occasional issuer documents. Its official files include:

- canonical CVM issuer code;
- document reference date;
- delivery date;
- category, type, species and subject metadata;
- protocol, version and download link when supplied by the source.

The official archive currently exposes annual files from 2003 onward. The loader uses only exact
`company_id=cvm:<Codigo_CVM>` identities and rejects schema drift for the target rows.

## Conservative availability contract

`Data_Entrega` supplies a date but not an intraday publication time. To avoid same-day look-ahead, the
collector assigns:

```text
available_from = Data_Entrega + 1 calendar day at 00:00 UTC
```

A document delivered on the COM date is therefore not treated as known during that COM session.

## What is compared

For every B3 stock-dividend, cash-dividend or subscription row whose `lastDatePrior` falls inside the
audit period, the audit records:

- the B3 source section and source index;
- label, `assetIssued`, ISIN, approval date and COM date;
- every CVM IPE document for the exact canonical issuer whose `Data_Referencia` equals `approvedOn`;
- which of those documents were conservatively available by the COM date.

These are deliberately called **corroboration candidates**, not event matches. Subjects and files are
not interpreted, keyword-matched or converted into economic terms. Multiple documents can legitimately
share the same issuer and reference date.

## Fail-closed boundaries

The audit always retains:

```text
CVM_IPE_DOCUMENTS_UNSTRUCTURED
CVM_IPE_SECURITY_CLASS_SCOPE_UNPROVEN
CVM_IPE_REVISION_HISTORY_COMPLETENESS_UNPROVEN
STRUCTURED_EVENT_HISTORY_COMPLETENESS_UNPROVEN
```

It can additionally emit:

```text
EVENT_APPROVAL_DATE_MISSING
EVENT_DOCUMENT_REFERENCE_DATE_NOT_FOUND
EVENT_DOCUMENT_NOT_AVAILABLE_BY_COM_DATE
UNSUPPORTED_SUBSCRIPTION_RIGHTS
```

The IPE index is issuer-level. Its metadata does not establish that a document applies to the exact
ordinary/preferred/unit security represented by a B3 row. It also does not expose normalized event
ratios, cash amounts, rights terms or a complete structured lifecycle.

Consequently, even perfect same-date corroboration leaves all of these false:

```text
structured_event_terms_available
security_class_resolution_proven
historical_event_source_completeness_proven
event_aware_return_path_ready
readiness_promotion_allowed
price_series_blocker_removed
```

## Commercial-source boundary

B3 documents a structured Corporate Events channel in
[UP2DATA](https://www.b3.com.br/pt_br/market-data-e-indices/servicos-de-dados/up2data/dados-disponiveis/).
Its Schedule, LifeCycle and Corporate Action files cover dividends, JCP, bonuses, splits, reverse
splits, subscriptions and other events. B3's
[access page](https://www.b3.com.br/pt_br/market-data-e-indices/servicos-de-dados/up2data/contratacao-e-acesso/)
requires a commercial contract. It is therefore evidence that a stronger structured source exists,
not a dependency silently introduced into this free-first project.

Any decision to contract or license that source is a separate cost and licensing decision.

## Live smoke

The workflow `cvm-ipe-corporate-action-ledger-audit-smoke` evaluates 2024–2025 for:

| B3 issuer | Ticker | Canonical identity |
|---|---|---|
| MGLU | MGLU3 | `cvm:22470` |
| ITSA | ITSA4 | `cvm:7617` |
| B3SA | B3SA3 | `cvm:21610` |
| AMER | AMER3 | `cvm:20990` |

The smoke fails if canonical identities drift, official archives contain no issuer documents, observed
B3 events disappear entirely, exact-date corroboration disappears entirely, or any diagnostic boundary
is promoted.

## Reproduction

```bash
python scripts/cvm_ipe_corporate_action_ledger_audit.py \
  --sample MGLU:MGLU3:22470 \
  --sample ITSA:ITSA4:7617 \
  --sample B3SA:B3SA3:21610 \
  --sample AMER:AMER3:20990 \
  --start-year 2024 \
  --end-year 2025 \
  --output cvm-ipe-corporate-action-ledger-audit.json
```
