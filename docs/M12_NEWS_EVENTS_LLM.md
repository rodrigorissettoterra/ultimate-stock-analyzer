# M12 — News, Corporate Events and LLM Classification

Status: **implemented in v1.2 candidate**.

## Pipeline

```text
articles / official disclosures
        ↓
URL exact-deduplication
        ↓
near-duplicate headline clustering
        ↓
representative selection (official > specialized > other)
        ↓
one LLM classification per cluster
        ↓
relevant 0/1 + impact + severity + confidence
        ↓
deterministic event score with time decay
```

The LLM never calculates the financial score. It only classifies unstructured evidence into a
validated `NewsSignal` contract. The event-scoring engine is deterministic Python.

## Why clustering happens before the LLM

The same material fact can be reported by many outlets. Counting each article separately creates
artificially large news impact and unnecessary LLM cost. M12 first removes URL duplicates and
clusters near-duplicate headlines within a configurable time window, then chooses one
representative article. Official evidence is preferred when available.

This is intentionally conservative: semantically equivalent events with very different headlines
may remain separate. Later evaluation can add embedding-assisted clustering without changing the
score contract.

## Source hierarchy

- **OFFICIAL** — CVM, B3 and company IR disclosures explicitly ingested as official evidence;
- **SPECIALIZED** — configured financial-news domains;
- **OTHER** — other public sources.

Company IR domains vary, so callers may explicitly mark an RI document as `OFFICIAL` instead of
relying on a hard-coded domain list.

Source tier affects evidence weight/confidence, never the direction of impact by itself.

## LLM output

Required structured fields remain:

- ticker;
- `relevant` (binary);
- event type;
- impact from -1 to +1;
- severity 1–5;
- confidence 0–1;
- rationale.

The prompt explicitly forbids buy/sell recommendations, target prices, score calculation and
invented missing facts.

## Time decay

Different events have different persistence. Defaults give longer half-lives to bankruptcy,
default, fraud/accounting, regulatory and M&A events than to earnings/dividend events. These
values are hypotheses pending M15/M16 validation.

## Public-repository and copyright safety

The repository publishes code, source registries, URLs, hashes/metadata and synthetic fixtures.
It does not redistribute article corpora. Runtime storage should prefer source URL, timestamps,
hashes, classification and short derived summaries; collection must respect each publisher's
terms and robots/access restrictions.
