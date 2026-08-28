# Definition of Done

A milestone is done only when implementation, tests, documentation and security/data-source implications are complete. Financial formulas require deterministic tests. Data ingestion requires source lineage and point-in-time fields. Any LLM output used by the model must be schema-validated and confidence-aware. No secrets or non-redistributable bulk data may be committed. A scoring change requires a model-version change and, after M15, regression/backtest comparison.
