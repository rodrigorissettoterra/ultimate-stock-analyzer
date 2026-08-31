# Post-M20 — SUSEP insurer expense and combined ratios

## Purpose

Promote the remaining underwriting expense metrics only after the administrative-expense source field and regulator formula are independently verified.

## Official field evidence

The permanent SUSEP schema smoke reads the official `Ses_campos.csv` dictionary. Its live artifact confirms current CMPID `4069` as `(-) DESPESAS ADMINISTRATIVAS`, accounting frame `23`, valid from `200301` through `210001`. Historical CMPID `542` carries the predecessor description but ended in `200212` and is not used by this current-era contract.

The same live archive manifest confirms `SES_Balanco.csv` exposes `coenti`, `damesano`, `cmpid`, `valor`, `seq`, and `quadro`. The administrative-expense observation is therefore selected by exact numeric SUSEP company code, exact December period and exact CMPID `4069`.

## Annualization and sign

Quad 23 is the insurer income-statement frame. As with the already verified net-income CMPID `518`, the annual accounting observation is the December YTD value; monthly accounting values are not summed.

The official dictionary explicitly marks CMPID `4069` as a negative expense line (`(-) DESPESAS ADMINISTRATIVAS`). The implementation therefore accepts only finite source values less than or equal to zero and converts `-DA` to a positive expense magnitude. A positive source value is not silently converted with `abs`; it fails closed to `UNKNOWN` because it may represent a reversal or another accounting condition requiring separate interpretation.

## Current-era SUSEP methodology

SUSEP market reports distinguish:

- sinistrality;
- IDC, the commercial-expense index;
- IDA, the administrative-expense index;
- IC, the combined ratio;
- ICA, the expanded combined ratio.

The regulator states that earned premium became gross of reinsurance from December 2013 and sinistrality began using incurred claims from the same point. Older methodology publications give the combined-ratio identity as `(claims + commercial expenses + administrative expenses) / earned premium`. To avoid a mixed-definition fiscal year, this project continues to begin the current contract at FY2014.

For one insurer and one complete fiscal year:

```text
PG = sum(premio_ganho)
SO = sum(sinistro_ocorrido)
DC = sum(desp_com)
DA = - December_YTD(CMPID 4069)

administrative_expense_ratio = DA / PG
expense_ratio = (DC + DA) / PG
combined_ratio = (SO + DC + DA) / PG
```

`expense_ratio` is intentionally total commercial plus administrative expenses. Mapping only `DC/PG` or only `DA/PG` to the model key would understate the operating expense burden represented in the combined ratio.

## Fail-closed independence

The existing underwriting dependency isolation remains mandatory:

- missing/corrupt claims disable `loss_ratio` and `combined_ratio`, but not `expense_ratio`;
- missing/corrupt commercial expenses disable `expense_ratio` and `combined_ratio`, but not `loss_ratio` or the supporting administrative index;
- missing/duplicate/invalid CMPID `4069` disables administrative, total-expense and combined ratios, but not the already verified loss/commercial metrics;
- the operating table still requires all 12 months for a valid annual denominator;
- exact numeric SUSEP identity only; no ticker/name/fuzzy fallback;
- no interpolation and no LLM-derived financial values.

## Point-in-time boundary

Current SES historical downloads can be reloaded and changed by the regulator. These derived metrics therefore remain:

```text
point_in_time_eligible = false
```

They may support current structural scoring, but not strict historical PIT backtesting until revision/publication-aware evidence is available.

## Coverage impact

In `insurance_v0.6.yml`:

- `expense_ratio` contributes 20% of the 30% underwriting category = **6 percentage points**;
- `combined_ratio` contributes 50% of the 30% underwriting category = **15 percentage points**.

Together these metrics can add 21pp of structural coverage. Combined with the previously verified 54pp, valid evidence can bring insurer potential coverage to **75%**. The ranking gate remains **65%** and the confidence gate remains **55%**; neither is lowered or bypassed. Passing a coverage gate does not imply empirical validation, point-in-time suitability, or an investment recommendation.
