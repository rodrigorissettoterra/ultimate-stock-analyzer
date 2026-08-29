from __future__ import annotations

import logging
import time

from ultimate_stock_analyzer.runtime.jobs import RetryPolicy, run_with_retry
from ultimate_stock_analyzer.runtime.logging import configure_logging
from ultimate_stock_analyzer.runtime.repository_factory import build_repository
from ultimate_stock_analyzer.runtime.settings import RuntimeSettings

logger = logging.getLogger(__name__)


def _require_repository_ready(repository: object) -> None:
    is_ready = getattr(repository, "is_ready", None)
    if not callable(is_ready) or not is_ready():
        raise RuntimeError("repository readiness check failed")


def main() -> None:
    settings = RuntimeSettings()
    configure_logging(settings.log_level)
    repository = build_repository(settings)
    logger.info("maintenance_worker_started", extra={"event": "maintenance_worker_started"})
    try:
        while True:
            run_with_retry(
                "repository_readiness",
                lambda: _require_repository_ready(repository),
                policy=RetryPolicy(max_attempts=3, initial_delay_seconds=1.0),
            )
            time.sleep(settings.worker_heartbeat_seconds)
    except KeyboardInterrupt:
        logger.info("maintenance_worker_stopped", extra={"event": "maintenance_worker_stopped"})


if __name__ == "__main__":
    main()
