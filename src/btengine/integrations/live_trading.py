"""Future seam: Demo/Live Trading Agents.

Not implemented. These ``Protocol``\\ s mirror the exact two seams the Core
Backtesting Engine already isolates behind — a candle source and an order
executor — so a live/demo agent can reuse everything else in this engine
(``PositionManager``, ``PortfolioState``, ``OrderManager``'s validation
half, ``StrategyContext``, the ``Strategy`` interface) unchanged, per
``docs/ARCHITECTURE.md``'s original design goal. Only these two concrete
implementations differ between backtesting and live trading; this module
fixes their shape ahead of time without building either.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Protocol, runtime_checkable

from btengine.backtest.events import FillEvent, OrderEvent
from btengine.data.schema import Candle


@runtime_checkable
class LiveMarketDataFeed(Protocol):
    """Live counterpart to
    :class:`~btengine.backtest.data_feed.HistoricalCandleFeed`: same
    "yield candles in chronological order" contract, backed by a live feed
    (websocket, polling) instead of the historical ``DataRepository``.
    """

    def iter_live(self) -> Iterator[Candle]:
        """Yield each new candle as it becomes available, in real time."""


@runtime_checkable
class LiveExecutionHandler(Protocol):
    """Live counterpart to
    :class:`~btengine.backtest.order_manager.OrderManager`'s fill
    simulation: same ``OrderEvent -> FillEvent`` contract, backed by a real
    exchange connection instead of a simulated next-bar fill.
    """

    def submit_order(self, order: OrderEvent) -> FillEvent:
        """Submit ``order`` to a real exchange and return its actual fill."""
