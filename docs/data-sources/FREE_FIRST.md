# Free-first source strategy

## Confirmed foundation

- CVM Open Data publishes annual structured DFP archives and ITR archives by year.
- B3 Public Data Hub exposes historical series and securities-lending areas, among other market datasets.
- Banco Central SGS provides public time series through JSON/CSV interfaces.

The implementation prefers stable official downloads and documented files over brittle scraping of rendered pages.

## Fundamentus

The optional `fundamentus` Python adapter is useful for rapid cross-checking and screening, including the workflow already demonstrated in the owner's `Biblioteca-Fundamentus` project. It is intentionally not the authoritative accounting source.

## Not yet adopted

No paid market-data, consensus, news or lending provider is included in v0.1. If later proposed, it must pass the paid-resource gate in `DATA_SOURCES.md`.
