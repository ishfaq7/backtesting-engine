"""Future seam: a web dashboard consuming backtest/live results.

Not implemented. This ``Protocol`` fixes the shape a future publisher must
satisfy to stream results somewhere a dashboard can read them (a
websocket, a message queue, a database) — the Core Backtesting Engine's
outputs (:class:`~btengine.backtest.engine.BacktestResult`, its equity
curve, its trade log) are already plain, serializable dataclasses, so a
future dashboard integration is a pure consumer of existing data, requiring
no changes to the engine itself.
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol, runtime_checkable

from btengine.backtest.engine import BacktestResult


@runtime_checkable
class DashboardPublisher(Protocol):
    """Something that forwards backtest results/progress to a dashboard."""

    def publish_result(self, result: BacktestResult) -> None:
        """Publish a completed backtest's final result."""

    def publish_equity_point(self, timestamp: datetime, equity: float) -> None:
        """Publish one incremental equity-curve point during a live/streaming run."""
