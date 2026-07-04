"""Reads already-cached historical candles and streams them in strict
chronological order across one or more symbols.

This is deliberately a thin read-only adapter over
:class:`~btengine.data.repository.DataRepository` — it never talks to a
provider (CoinGlass or otherwise) and never fetches anything over the
network. A backtest run assumes the required range has already been
synced (via ``btengine.data.sync.HistoricalDataService``) before it starts;
that separation keeps "acquiring data" and "replaying data" as independent
concerns.

Multiple symbols are merged with a k-way heap merge keyed on timestamp, so
"support multiple assets" holds today, not just as a future extension: the
engine sees one strictly time-ordered stream regardless of how many
symbols are configured.
"""

from __future__ import annotations

import heapq
import itertools
from collections.abc import Iterator, Sequence
from datetime import datetime

from btengine.data.repository import DataRepository
from btengine.data.schema import Candle, Timeframe


class HistoricalCandleFeed:
    """Streams cached candles for one or more symbols in chronological order."""

    def __init__(
        self,
        repository: DataRepository,
        *,
        exchange: str,
        symbols: Sequence[str],
        timeframe: Timeframe,
        start: datetime,
        end: datetime,
    ) -> None:
        if not symbols:
            raise ValueError("symbols must not be empty")
        self._repository = repository
        self._exchange = exchange
        self._symbols = list(symbols)
        self._timeframe = timeframe
        self._start = start
        self._end = end

    def iter_chronological(self) -> Iterator[Candle]:
        """Yield every cached candle across all configured symbols, in
        strict timestamp order. Ties are broken by symbol name so iteration
        order is deterministic run-to-run.
        """
        streams: dict[str, Iterator[Candle]] = {
            symbol: iter(
                self._repository.read(
                    Candle,
                    exchange=self._exchange,
                    symbol=symbol,
                    timeframe=self._timeframe,
                    start=self._start,
                    end=self._end,
                )
            )
            for symbol in self._symbols
        }

        # counter breaks ties deterministically without ever comparing Candle
        # objects directly (Candle has no total ordering defined).
        tie_breaker = itertools.count()
        heap: list[tuple[datetime, str, int, Candle]] = []

        for symbol, stream in streams.items():
            candle = next(stream, None)
            if candle is not None:
                heapq.heappush(heap, (candle.timestamp, symbol, next(tie_breaker), candle))

        while heap:
            _, symbol, _, candle = heapq.heappop(heap)
            yield candle
            next_candle = next(streams[symbol], None)
            if next_candle is not None:
                heapq.heappush(heap, (next_candle.timestamp, symbol, next(tie_breaker), next_candle))
