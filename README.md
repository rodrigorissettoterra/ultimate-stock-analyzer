# Ultimate Stock Analyzer

An open, free-first and auditable research engine for Brazilian equities. The project separates **company quality**, **investment attractiveness at the current price**, and **entry timing**, combining deterministic financial calculations with LLM-assisted analysis of textual evidence.

> **Status:** v0.4 — CVM point-in-time fundamentals plus dividend/JCP regularity and sustainability. This is research software, not individualized investment advice and not a promise of future returns.

## Design principles

- **Evidence > models > LLM.** The LLM never invents or calculates authoritative financial metrics.
- **Free-first.** CVM, B3, Banco Central and other public sources come before paid data providers.
- **Point-in-time.** Every observation carries reference, publication/availability and collection timestamps to support honest backtests.
- **Public-by-design.** No API keys, credentials, licensed datasets or private data are committed.
- **Sector-aware.** Banks, insurers, utilities, commodity producers and industrial companies are not scored with identical rules.
- **Auditable.** Scores are decomposable into categories and underlying metrics.
- **Abstention is valid.** Missing or conflicting data lowers confidence; severe red flags may block an investment classification.

## Current capabilities

- CVM issuer master using stable `CD_CVM` identity and FCA-based security records.
- CVM DFP/ITR/FCA ingestion with document versions and receipt timestamps.
- Point-in-time financial statement normalization that prevents future-information leakage.
- Exact CVM fixed-account extraction with source-line lineage.
- Broad deterministic metrics: growth, margins, ROE/ROA/ROIC/ROCE, liquidity, leverage, cash flow, payout sustainability, efficiency and cash conversion cycle.
- General-corporate input contract with explicit bank/insurer exclusion pending sector models.
- B3 public corporate-action adapter for cash dividends/JCP with explicit source/date semantics.
- Dividend regularity, streak/gap history, extraordinary dependence, TTM yield and annual stability.
- Dividend sustainability score using earnings/FCF coverage rather than yield alone.
- Point-in-time filtering of dividend announcements for leakage-safe research.
- Cross-sectional, sector-aware percentile scoring with configurable metric direction and weights.
- Separate quality, valuation, entry, news, rental, liquidity, risk and confidence dimensions.
- Deterministic composite scoring and red-flag blocking.
- OpenAI-compatible news/event classifier with strict structured output and no numeric score calculation by the LLM.
- Banco Central SGS collector.
- FastAPI endpoints for health, scoring and ranking.
- Synthetic end-to-end examples and deterministic unit tests.
- Fundamentus adapter retained only as a fallback/cross-check.

## Quick start

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux/macOS: source .venv/bin/activate
pip install -e ".[dev]"
pytest
uvicorn ultimate_stock_analyzer.api.main:app --reload
```

Optional free Fundamentus adapter:

```bash
pip install -e ".[fundamentus]"
ultimate-stock-analyzer screen-dividends --min-dy 0.04 --max-candidates 50
```

Run the synthetic example:

```bash
python examples/demo_ranking.py
```

## Repository layout

```text
src/ultimate_stock_analyzer/
  collectors/       public-source ingestion adapters
  normalization/    canonical point-in-time financial normalization
  fundamentals/     deterministic formulas and CVM accounting contracts
  dividends/        dividend/JCP regularity and sustainability
  market/           entry and market-derived calculations
  news/             LLM-assisted event analysis
  scoring/          normalization and scoring engine
  orchestration/    end-to-end analysis services
  api/              FastAPI interface
config/scoring/      versioned model configuration
docs/                architecture, model specification and data registry
tests/               deterministic test suite
```

## Data policy

The Git repository does **not** act as a financial data lake. Collectors reconstruct data from original sources. Raw and processed datasets are gitignored. See [`DATA_SOURCES.md`](DATA_SOURCES.md) and [`SECURITY.md`](SECURITY.md).

## License

Code is licensed under the Apache License 2.0. Third-party data remains subject to the terms and rights of its original providers.
