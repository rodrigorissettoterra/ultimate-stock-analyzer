# M8 — Market / Entry Timing

Status: **implemented in v0.8**.

## Objective

M8 answers a different question from M5/M6 and M7:

- Structural Score: is this a high-quality business?
- Valuation Score: is the security attractive at the current price relative to estimated value?
- Entry Score: is the current market setup favorable, or is price temporarily extended/speculative?

Entry timing never changes the Structural Score.

## Free-first market data

The primary historical-price source is the public B3 COTAHIST series. The parser implements the
245-character fixed-width public layout and retains ticker, date, OHLC, trades, quantity, volume
and ISIN.

B3 explicitly states that historical quotes are not adjusted for inflation or issuer corporate
events such as dividends, bonuses and subscription rights. The project therefore keeps raw
`close` separate from optional `adjusted_close`. Raw values are never silently relabeled as
adjusted prices.

## Indicators

The deterministic engine calculates, when data is available:

- SMA50 and SMA200;
- RSI14;
- 5, 20 and 60-session returns;
- 60-session daily volatility;
- current volume / prior 20-session average volume;
- volatility-standardized 5 and 20-session returns;
- distance from SMA200;
- drawdown from the recent 52-week high.

## Speculation Risk

`SpeculationRisk` combines four observable signals:

1. unusually positive 5-session return relative to recent volatility;
2. unusually positive 20-session return relative to recent volatility;
3. abnormal volume;
4. large positive extension above SMA200.

A confirmed material event can reduce the part of the risk attributed to an unexplained move,
but it never automatically sets risk to zero. If event context is unknown, the result is flagged.

## Entry Score

The v0.8 hypothesis weights are:

- valuation: 35%;
- trend: 20%;
- RSI: 15%;
- pullback/20-session extension: 15%;
- speculation safety: 15%.

Missing components reduce coverage. Short history and unadjusted prices reduce confidence. A
high speculation risk can force `EXTENDED_SPECULATIVE` even when valuation is attractive.

## Calibration warning

These weights and thresholds are not presented as optimal. M15/M16 must validate them using
point-in-time data and walk-forward testing. Technical signals are contextual risk/timing inputs,
not independent buy/sell predictions.
