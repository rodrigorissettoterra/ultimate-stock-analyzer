CREATE TABLE IF NOT EXISTS analysis_snapshots (
    ticker TEXT NOT NULL,
    as_of DATE NOT NULL,
    model_version TEXT NOT NULL,
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (ticker, as_of, model_version)
);

CREATE INDEX IF NOT EXISTS analysis_snapshots_latest_idx
    ON analysis_snapshots (ticker, as_of DESC, created_at DESC);

CREATE TABLE IF NOT EXISTS backtest_snapshots (
    backtest_id TEXT PRIMARY KEY,
    end_date DATE NOT NULL,
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS backtest_snapshots_end_date_idx
    ON backtest_snapshots (end_date DESC);
