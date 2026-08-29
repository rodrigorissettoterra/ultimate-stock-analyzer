# M19 — Conversational Agent

Status: **implemented candidate**.

M19 adds a conversational explanation layer without giving the LLM authority over financial
calculation or retrieval decisions.

## Pipeline

1. deterministic planner identifies stock, comparison, ranking or backtest intent;
2. the query service retrieves already-published API-domain objects;
3. a verified context is assembled with data dates, model versions and evidence references;
4. a synthesizer writes the answer;
5. the API returns answer text plus intent, tickers, confidence, data date, model versions and
   citations.

## LLM optionality

When `USA_LLM_API_KEY` and `USA_LLM_MODEL` are configured, the agent uses the OpenAI-compatible
synthesizer. Otherwise it uses deterministic templates. The API key is read from the environment and
is never sent to the browser or committed to the repository.

## Guardrails

The synthesis prompt explicitly forbids changing/recalculating scores, dates, status, ranking or
sources and forbids imperative buy/sell recommendations. Missing evidence must remain missing.

## Endpoint

`POST /v1/agent/query`

Example request:

```json
{"question": "Compare PETR4 e VALE3"}
```

The response remains structured even when an LLM is used, so downstream clients do not need to
parse prose to recover tickers, confidence or citations.
