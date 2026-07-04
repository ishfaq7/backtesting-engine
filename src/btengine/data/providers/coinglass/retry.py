"""Retry executor with exponential backoff and jitter.

Only *retryable* failures are retried: :class:`TransientProviderError`
(timeouts, connection errors, 5xx) and :class:`RateLimitExceededError`
(429, or the local limiter signaling exhaustion). Every other exception
(auth failures, invalid responses, normalization errors, configuration
errors) is fatal and propagates on the first attempt, since retrying a
malformed request or a bad API key can never succeed.
"""

from __future__ import annotations

import random
import time
from typing import Callable, TypeVar

from btengine.data.errors import RateLimitExceededError, TransientProviderError

T = TypeVar("T")


class RetryPolicy:
    def __init__(
        self,
        *,
        max_retries: int,
        base_delay_seconds: float,
        max_delay_seconds: float,
        sleep: Callable[[float], None] = time.sleep,
        jitter: Callable[[], float] = random.random,
    ) -> None:
        if max_retries < 0:
            raise ValueError("max_retries must be >= 0")
        if base_delay_seconds <= 0 or max_delay_seconds <= 0:
            raise ValueError("delay bounds must be positive")
        self._max_retries = max_retries
        self._base_delay_seconds = base_delay_seconds
        self._max_delay_seconds = max_delay_seconds
        self._sleep = sleep
        self._jitter = jitter

    def _backoff_delay(self, attempt: int) -> float:
        exponential = self._base_delay_seconds * (2**attempt)
        capped = min(exponential, self._max_delay_seconds)
        # Full jitter in [0.5x, 1.0x] of the capped delay avoids thundering-herd
        # retries while still respecting the exponential ceiling.
        return capped * (0.5 + self._jitter() * 0.5)

    def run(self, operation: Callable[[], T]) -> T:
        """Execute ``operation``, retrying retryable failures up to ``max_retries`` times."""
        attempt = 0
        while True:
            try:
                return operation()
            except RateLimitExceededError as exc:
                if attempt >= self._max_retries:
                    raise
                delay = (
                    exc.retry_after_seconds
                    if exc.retry_after_seconds is not None
                    else self._backoff_delay(attempt)
                )
                self._sleep(delay)
                attempt += 1
            except TransientProviderError:
                if attempt >= self._max_retries:
                    raise
                self._sleep(self._backoff_delay(attempt))
                attempt += 1
