# M18 — Dashboard

Status: **implemented candidate**.

The dashboard is a dependency-light web client served by the FastAPI process at `/dashboard/`.
There is no Node build step, CDN dependency or direct database access.

## Views

The first release provides:

- investment-attractiveness ranking;
- filters for sector, status, minimum score and rankability;
- company quality, investment attractiveness, entry timing and data confidence side by side;
- price, TTM dividend yield and lending rate in the ranking;
- stock detail dialog with component scores and provenance references;
- published backtest summaries;
- responsive layout for desktop and mobile;
- keyboard navigation and a skip link;
- light/dark adaptation through system preference.

## Architecture

The browser only calls `/v1`. It does not know database credentials or LLM keys and cannot invoke
collectors or scoring engines directly. This keeps presentation independent from calculation and
supports the public-repository security model.

## Empty-state behavior

The default in-memory API repository is empty, so a clean checkout shows an empty ranking until a
real persistence adapter or notebook-provided repository is configured. Synthetic data is not
silently presented as current market analysis.
