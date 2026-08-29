from __future__ import annotations

from ultimate_stock_analyzer.api.repository import AnalysisRepository, InMemoryAnalysisRepository
from ultimate_stock_analyzer.runtime.settings import RuntimeSettings


def build_repository(settings: RuntimeSettings) -> AnalysisRepository:
    if not settings.database_url.strip():
        return InMemoryAnalysisRepository()
    from ultimate_stock_analyzer.storage.postgres_repository import PostgresAnalysisRepository

    return PostgresAnalysisRepository(settings.database_url)
