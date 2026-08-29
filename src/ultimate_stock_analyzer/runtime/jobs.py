from __future__ import annotations

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import TypeVar
from uuid import uuid4

T = TypeVar("T")
logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    max_attempts: int = 3
    initial_delay_seconds: float = 1.0
    max_delay_seconds: float = 30.0

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be positive")
        if self.initial_delay_seconds < 0 or self.max_delay_seconds < 0:
            raise ValueError("retry delays cannot be negative")


def run_with_retry(
    job_name: str,
    operation: Callable[[], T],
    *,
    policy: RetryPolicy | None = None,
    sleep: Callable[[float], None] = time.sleep,
) -> T:
    retry = policy or RetryPolicy()
    run_id = str(uuid4())
    delay = retry.initial_delay_seconds
    for attempt in range(1, retry.max_attempts + 1):
        started = time.perf_counter()
        try:
            result = operation()
        except Exception:
            duration_ms = (time.perf_counter() - started) * 1000.0
            logger.exception(
                "job_attempt_failed",
                extra={
                    "event": "job_attempt_failed",
                    "job": job_name,
                    "run_id": run_id,
                    "attempt": attempt,
                    "duration_ms": round(duration_ms, 3),
                },
            )
            if attempt >= retry.max_attempts:
                raise
            sleep(delay)
            delay = min(retry.max_delay_seconds, max(delay * 2.0, retry.initial_delay_seconds))
        else:
            duration_ms = (time.perf_counter() - started) * 1000.0
            logger.info(
                "job_completed",
                extra={
                    "event": "job_completed",
                    "job": job_name,
                    "run_id": run_id,
                    "attempt": attempt,
                    "duration_ms": round(duration_ms, 3),
                },
            )
            return result
    raise RuntimeError("unreachable retry state")
