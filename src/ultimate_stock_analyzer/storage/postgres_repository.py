from __future__ import annotations

from collections.abc import Iterable
from typing import Any

import psycopg
from psycopg.types.json import Jsonb

from ultimate_stock_analyzer.api.schemas import BacktestSummary, StockAnalysis


class PostgresAnalysisRepository:
    def __init__(self, database_url: str) -> None:
        if not database_url.strip():
            raise ValueError("database_url is required")
        self.database_url = database_url

    def _connect(self) -> psycopg.Connection[Any]:
        return psycopg.connect(self.database_url)

    def is_ready(self) -> bool:
        try:
            with self._connect() as connection:
                connection.execute("SELECT 1").fetchone()
        except psycopg.Error:
            return False
        return True

    def list_stock_analyses(self) -> list[StockAnalysis]:
        sql = """
            SELECT DISTINCT ON (ticker) payload
            FROM analysis_snapshots
            ORDER BY ticker, as_of DESC, created_at DESC
        """
        with self._connect() as connection:
            rows = connection.execute(sql).fetchall()
        return [StockAnalysis.model_validate(row[0]) for row in rows]

    def get_stock_analysis(self, ticker: str) -> StockAnalysis | None:
        sql = """
            SELECT payload
            FROM analysis_snapshots
            WHERE ticker = %s
            ORDER BY as_of DESC, created_at DESC
            LIMIT 1
        """
        with self._connect() as connection:
            row = connection.execute(sql, (ticker.upper(),)).fetchone()
        return StockAnalysis.model_validate(row[0]) if row else None

    def list_backtests(self) -> list[BacktestSummary]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT payload FROM backtest_snapshots ORDER BY end_date DESC, backtest_id"
            ).fetchall()
        return [BacktestSummary.model_validate(row[0]) for row in rows]

    def get_backtest(self, backtest_id: str) -> BacktestSummary | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT payload FROM backtest_snapshots WHERE backtest_id = %s",
                (backtest_id,),
            ).fetchone()
        return BacktestSummary.model_validate(row[0]) if row else None

    def upsert_stock_analyses(self, analyses: Iterable[StockAnalysis]) -> None:
        sql = """
            INSERT INTO analysis_snapshots (ticker, as_of, model_version, payload)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (ticker, as_of, model_version)
            DO UPDATE SET payload = EXCLUDED.payload, created_at = now()
        """
        rows = [
            (
                row.ticker.upper(),
                row.as_of,
                row.scores.model_version,
                Jsonb(row.model_dump(mode="json")),
            )
            for row in analyses
        ]
        if not rows:
            return
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.executemany(sql, rows)
            connection.commit()

    def upsert_backtests(self, backtests: Iterable[BacktestSummary]) -> None:
        sql = """
            INSERT INTO backtest_snapshots (backtest_id, end_date, payload)
            VALUES (%s, %s, %s)
            ON CONFLICT (backtest_id)
            DO UPDATE SET end_date = EXCLUDED.end_date, payload = EXCLUDED.payload, created_at = now()
        """
        rows = [
            (row.backtest_id, row.end_date, Jsonb(row.model_dump(mode="json"))) for row in backtests
        ]
        if not rows:
            return
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.executemany(sql, rows)
            connection.commit()
