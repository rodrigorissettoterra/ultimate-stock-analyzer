# M5 — Structural Score v0.5

## Purpose

The Structural Score answers one narrow question:

> How strong is the company as a long-horizon operating and financial asset relative to relevant peers?

It intentionally does **not** answer whether the share is cheap today or whether today is a good
entry point. Those belong to valuation and entry layers.

## What is excluded by design

The following do not affect Structural Score v0.5:

- current share price;
- P/E, P/B, EV/EBIT, DCF or margin of safety;
- current dividend yield;
- RSI, moving averages or momentum;
- news sentiment/events;
- securities-lending rate or short pressure;
- macro timing signals.

Dividend regularity and sustainability may enter because they describe a long-horizon distribution
policy and cash-generation quality. Dividend **yield** does not, because it is price-dependent.

## Current category hypothesis

| Category | Initial weight |
|---|---:|
| Profitability | 25% |
| Financial strength | 25% |
| Cash flow | 20% |
| Growth | 15% |
| Dividend quality | 15% |

These are versioned hypotheses, not optimized weights. M10 will add accounting/governance evidence,
M6 will create sector-specific models, and M15/M16 will validate/calibrate the model point-in-time.

## Peer normalization

Higher/lower-is-better metrics are ranked within sector. Ties receive their true average empirical
rank. Percentile scores from small peer groups are shrunk toward 50:

`adjusted = 50 + reliability × (raw_percentile - 50)`

where reliability reaches 1.0 at the configured minimum peer count (8 by default). This prevents a
company from receiving an extreme 0/100 score merely because only two or three peers have data.

Target-shaped metrics use explicit economic targets instead of peer percentiles.

## Missing data and ranking eligibility

Missing inputs are never imputed silently. Each category reports data coverage. Structural Score is
computed from evidenced category weight only, while overall coverage and confidence remain separate.
A company is excluded from the rankable list when either:

- weighted structural coverage is below 65%; or
- structural confidence is below 55%.

The company can still be displayed with flags so the absence of evidence is visible rather than
converted into a false negative or false positive.

## Sector boundary

v0.5 is a generic/general-corporate scoring contract. Banks, insurers and other economically
specialized business models require the dedicated M6 model selector and sector-specific metrics
before production ranking. No claim is made that the v0.5 weights are valid for those sectors.
