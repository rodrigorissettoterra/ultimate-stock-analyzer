# M7 — Valuation

Status: **implemented in v0.7**.

## Objective

M7 answers a question that is deliberately separate from M5/M6 structural quality:

> Is the security attractive at the current market price?

A high-quality company can be expensive. A weak company can be statistically cheap. Structural
quality and valuation therefore remain independent signals until the integrated model in M14.

## Multi-model framework

The engine never treats one valuation formula as truth. Sector policies define an auditable set
of accepted methods and hypothesis weights:

- general corporates: FCFF DCF + peer P/E + peer EV/EBITDA + peer P/FCF;
- banks: residual income + peer P/B + peer P/E;
- insurers: residual income + peer P/B + peer P/E + DDM;
- utilities: FCFF DCF + DDM + peer EV/EBITDA + peer P/E;
- commodities: normalized mid-cycle DCF + mid-cycle EV/EBITDA, P/E and P/FCF.

The formulas are deterministic. Forecast growth, discount rates, target multiples and normalized
mid-cycle inputs must be supplied explicitly from upstream data/scenario modules; the LLM is not
allowed to invent them.

## Core formulas

`discounted_cash_flow_per_share` discounts explicit FCFF forecasts and terminal value, subtracts
net debt and divides by diluted shares.

`two_stage_ddm_per_share` values explicit dividend forecasts plus a Gordon terminal value.

`residual_income_per_share` starts from book value and discounts returns above/below the cost of
equity. This is the preferred intrinsic framework for banks and is also available to insurers.

The module also exposes deterministic equity-multiple and enterprise-multiple conversion helpers.

## Robust aggregation

Every `ValuationEstimate` contains a model id, fair value, model confidence, optional low/high
range, assumptions and provenance.

The sector policy rejects models that are inappropriate for that family. For example, a bank
estimate labelled `ev_ebitda_peer` is ignored even if supplied by an upstream component.

The blended value uses a confidence-adjusted **weighted median** rather than a simple mean. This
reduces sensitivity to a single extreme model. Model disagreement remains visible through a
relative median absolute deviation and the flag `HIGH_VALUATION_MODEL_DISPERSION`.

Coverage and confidence gates can force `INSUFFICIENT_DATA`; missing methods are never replaced by
LLM guesses.

## Margin of safety

`margin_of_safety = fair_value / market_price - 1`

The 0–100 valuation score is a transparent piecewise mapping of margin of safety. It is not a
forecast of future return. The fair value is invariant to market price; changing price changes
only margin of safety, score and valuation status.

## Calibration warning

The v0.7 model weights, score anchors and status thresholds are explicit hypotheses. They must be
validated in M15/M16 using point-in-time and walk-forward tests before being interpreted as
empirically calibrated.
