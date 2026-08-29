import json
import logging

import pytest
from fastapi.testclient import TestClient

from ultimate_stock_analyzer.api.main import create_app
from ultimate_stock_analyzer.api.repository import InMemoryAnalysisRepository
from ultimate_stock_analyzer.runtime.jobs import RetryPolicy, run_with_retry
from ultimate_stock_analyzer.runtime.logging import JsonLogFormatter
from ultimate_stock_analyzer.runtime.settings import RuntimeSettings


def test_production_settings_fail_closed_without_database() -> None:
    with pytest.raises(ValueError, match="USA_DATABASE_URL"):
        RuntimeSettings(env="production", database_url="", _env_file=None)


def test_retry_runner_recovers_without_sleeping_in_test() -> None:
    attempts = 0

    def flaky() -> str:
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise RuntimeError("temporary")
        return "ok"

    result = run_with_retry(
        "test_job",
        flaky,
        policy=RetryPolicy(max_attempts=3, initial_delay_seconds=1.0),
        sleep=lambda _: None,
    )
    assert result == "ok"
    assert attempts == 3


def test_json_formatter_emits_structured_fields() -> None:
    record = logging.LogRecord("test", logging.INFO, __file__, 1, "hello", (), None)
    record.request_id = "abc"
    payload = json.loads(JsonLogFormatter().format(record))
    assert payload["message"] == "hello"
    assert payload["request_id"] == "abc"


def test_readiness_and_request_id_are_exposed() -> None:
    client = TestClient(
        create_app(
            repository=InMemoryAnalysisRepository(),
            settings=RuntimeSettings(env="test", _env_file=None),
        )
    )
    response = client.get("/ready")
    assert response.status_code == 200
    assert response.json()["status"] == "ready"
    assert response.headers["X-Request-ID"]
