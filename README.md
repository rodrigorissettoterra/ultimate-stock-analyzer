# Ultimate Stock Analyzer

An open, free-first and auditable research engine for Brazilian equities. The project separates **company quality**, **investment attractiveness at the current price**, and **entry timing**, combining deterministic financial calculations with LLM-assisted analysis of textual evidence.

> **Status:** v0.1 foundation + executable scoring core. This is research software, not individualized investment advice and not a promise of future returns.

## Design principles

- **Evidence > models > LLM.** The LLM never invents or calculates authoritative financial metrics.
- **Free-first.** CVM, B3, Banco Central and other public sources come before paid data providers.
- **Point-in-time.** Every observation carries reference, publication/availability and collection timestamps to support honest backtests.
- **Public-by-design.** No API keys, credentials, licensed datasets or private data are committed.
- **Sector-aware.** Banks, insurers, utilities, commodity producers and industrial companies are not scored with identical rules.
- **Auditable.** Scores are decomposable into categories and underlying metrics.
- **Abstention is valid.** Missing or conflicting data lowers confidence; severe red flags may block an investment classification.

## Current capabilities

- Core financial formulas: margins, ROE, ROIC, leverage, FCF, CAGR and coverage ratios.
- Dividend regularity profile over configurable windows.
- Cross-sectional, sector-aware percentile scoring with configurable metric direction and weights.
- Separate quality, valuation, entry, news, rental, liquidity, risk and confidence dimensions.
- Deterministic composite scoring and red-flag blocking.
- OpenAI-compatible news/event classifier with strict structured output and no numeric score calculation by the LLM.
- CVM DFP/ITR public ZIP collector and Banco Central SGS collector.
- FastAPI endpoints for health, scoring and ranking.
- Synthetic end-to-end example and unit tests.
- Executable free-source dividend screener (`ultimate-stock-analyzer screen-dividends`) using Fundamentus only as a fallback/cross-check adapter.

## Quick start

```bash
python -m venv .venv
# Windows: .venv\\Scripts\\activate
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
  fundamentals/     deterministic financial formulas
  dividends/        dividend/JCP regularity analysis
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
