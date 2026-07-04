"""Token-bucket rate limiter enforcing CoinGlass's per-window request limits.

The clock and sleep functions are injectable so tests can exercise the
limiter's behavior without real wall-clock delays.
"""

from __future__ import annotations

import threading
import time
from typing import Callable


class TokenBucketRateLimiter:
    """Blocks callers until a request token is available.

    ``max_requests`` tokens are available per ``period_seconds``; tokens
    refill continuously (not in discrete bursts) so a caller making steady
    requests never has to wait a full period.
    """

    def __init__(
        self,
        max_requests: int,
        period_seconds: float,
        *,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if max_requests <= 0:
            raise ValueError("max_requests must be positive")
        if period_seconds <= 0:
            raise ValueError("period_seconds must be positive")
        self._max_requests = max_requests
        self._refill_rate_per_second = max_requests / period_seconds
        self._clock = clock
        self._sleep = sleep
        self._tokens = float(max_requests)
        self._last_refill = clock()
        self._lock = threading.Lock()

    def _refill_locked(self) -> None:
        now = self._clock()
        elapsed = max(0.0, now - self._last_refill)
        self._tokens = min(
            float(self._max_requests), self._tokens + elapsed * self._refill_rate_per_second
        )
        self._last_refill = now

    def acquire(self) -> None:
        """Consume one token, sleeping first if none is currently available."""
        while True:
            with self._lock:
                self._refill_locked()
                if self._tokens >= 1:
                    self._tokens -= 1
                    return
                wait_seconds = (1 - self._tokens) / self._refill_rate_per_second
            self._sleep(wait_seconds)

    @property
    def available_tokens(self) -> float:
        with self._lock:
            self._refill_locked()
            return self._tokens
