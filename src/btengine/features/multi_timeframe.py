"""Multi-timeframe historical data access.

Composes several :class:`~btengine.strategy.context.HistoryView` instances
(one per :class:`~btengine.data.schema.Timeframe`) behind one read-only
interface, so a feature analyzer (or a future strategy component) can look
at, say, 1h market structure while trading on 15m — without the Core
Backtesting Engine or the ``Strategy.on_market_event`` interface changing
at all. This is pure composition over the existing, unmodified
``HistoryView``: every lookahead guarantee it already provides carries
through unchanged.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime

from btengine.data.repository import DataRepository
from btengine.data.schema import Candle, Timeframe
from btengine.strategy.context import ClockLike, HistoryView


class MultiTimeframeView:
    """Read-only access to historical candles across several timeframes."""

    def __init__(self, views: Mapping[Timeframe, HistoryView]) -> None:
        if not views:
            raise ValueError("views must not be empty")
        self._views = dict(views)

    @property
    def timeframes(self) -> frozenset[Timeframe]:
        return frozenset(self._views)

    def get_candles(
        self,
        timeframe: Timeframe,
        *,
        lookback_periods: int | None = None,
        start: datetime | None = None,
    ) -> list[Candle]:
        """Return candles for ``timeframe``, delegating to that timeframe's
        underlying :class:`HistoryView` (same lookahead-safe semantics).
        """
        view = self._views.get(timeframe)
        if view is None:
            raise KeyError(
                f"No HistoryView configured for timeframe {timeframe.value}; "
                f"available: {sorted(tf.value for tf in self._views)}"
            )
        return view.get_candles(lookback_periods=lookback_periods, start=start)


def build_multi_timeframe_view(
    repository: DataRepository,
    clock: ClockLike,
    *,
    exchange: str,
    symbol: str,
    timeframes: Sequence[Timeframe],
) -> MultiTimeframeView:
    """Convenience factory: one :class:`HistoryView` per requested timeframe,
    all sharing the same repository, clock, exchange, and symbol.
    """
    views = {
        timeframe: HistoryView(repository, clock, exchange=exchange, symbol=symbol, timeframe=timeframe)
        for timeframe in timeframes
    }
    return MultiTimeframeView(views)
