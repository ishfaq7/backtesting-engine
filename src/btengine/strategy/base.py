"""The single interface a strategy plugin must implement.

The engine depends on nothing else about a strategy: it calls
``on_market_event`` with a :class:`~btengine.strategy.context.StrategyContext`
and consumes whatever :class:`~btengine.backtest.events.SignalEvent` objects
come back. It never inspects, imports, or reflects into a plugin's internal
analyzers, scoring model, or risk rules — none of that exists from the
engine's point of view.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence

from btengine.backtest.events import SignalEvent
from btengine.strategy.context import StrategyContext


class Strategy(ABC):
    """Abstract base every strategy plugin implements."""

    @abstractmethod
    def on_market_event(self, context: StrategyContext) -> Sequence[SignalEvent]:
        """Return zero or more signals in response to one fully-closed candle."""
