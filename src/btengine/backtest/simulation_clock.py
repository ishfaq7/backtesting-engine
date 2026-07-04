"""Tracks the current point in simulated time.

Every lookahead-prevention mechanism in the engine (bounded historical
queries, next-bar-only fills) is ultimately anchored to this clock. It is
intentionally minimal: it only ever advances, never rewinds, which turns
"a candle was processed out of order" into an immediate, loud failure
instead of a silent lookahead bug.
"""

from __future__ import annotations

from datetime import datetime

from btengine.backtest.errors import ClockError


class SimulationClock:
    """A monotonically non-decreasing clock representing "now" in the backtest."""

    def __init__(self, start_time: datetime) -> None:
        if start_time.tzinfo is None:
            raise ClockError("SimulationClock requires a timezone-aware start_time")
        self._current_time = start_time

    @property
    def now(self) -> datetime:
        return self._current_time

    def advance_to(self, timestamp: datetime) -> None:
        """Move the clock forward to ``timestamp``.

        Raises :class:`~btengine.backtest.errors.ClockError` if ``timestamp``
        is before the current time — this would mean a candle arrived out
        of chronological order, which the engine must never tolerate.
        """
        if timestamp < self._current_time:
            raise ClockError(
                f"Cannot move simulation clock backwards: "
                f"current={self._current_time.isoformat()} requested={timestamp.isoformat()}"
            )
        self._current_time = timestamp
