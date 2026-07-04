"""A minimal FIFO event queue.

Deliberately does nothing but hold and hand back events in the order they
arrived. Dispatch logic (deciding what each event type means and what to do
about it) lives in :mod:`~btengine.backtest.engine` — this class has no
knowledge of market events, signals, orders, or fills, only of ``Event``.
"""

from __future__ import annotations

from collections import deque

from btengine.backtest.events import Event


class EventLoop:
    """FIFO queue of pending events for the current simulation step."""

    def __init__(self) -> None:
        self._queue: deque[Event] = deque()

    def push(self, event: Event) -> None:
        self._queue.append(event)

    def pop(self) -> Event | None:
        return self._queue.popleft() if self._queue else None

    def __len__(self) -> int:
        return len(self._queue)

    def is_empty(self) -> bool:
        return len(self._queue) == 0
