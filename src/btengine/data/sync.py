"""Historical data loader with cache-first fetch and gap detection.

``HistoricalDataService`` is the single, reusable entry point for obtaining
historical market data — the same instance (or another built the same way)
is meant to be used by the Backtesting Engine, and later the Demo and Live
Trading Agents, so that all three read data from the same cache-first,
gap-checked path instead of each re-implementing fetch/cache logic.

Given a record type, symbol, exchange, timeframe, and date range, it reads
whatever is already cached, detects which expected timestamps are missing,
fetches *only* those missing sub-ranges from the provider, stores the
result, and returns the fully merged range from the cache. This keeps
CoinGlass API usage low while still catching partial/incomplete data (a
provider outage, a bad prior sync) instead of silently proceeding over gaps.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Callable, TypeVar

from btengine.data.base import MarketDataProvider
from btengine.data.repository import DataRepository
from btengine.data.schema import (
    Candle,
    CanonicalRecord,
    FundingRate,
    Liquidation,
    LongShortRatio,
    OpenInterest,
    Timeframe,
)

logger = logging.getLogger("btengine.data.sync")

RecordT = TypeVar("RecordT", bound=CanonicalRecord)


@dataclass(frozen=True)
class DataGap:
    """A contiguous stretch of missing expected records, inclusive bounds."""

    start: datetime
    end: datetime


def find_gaps(
    timestamps: list[datetime],
    *,
    expected_interval: timedelta,
    range_start: datetime,
    range_end: datetime,
) -> list[DataGap]:
    """Compare ``timestamps`` against the fully-populated grid implied by
    ``expected_interval`` over ``[range_start, range_end]`` and return the
    missing stretches as contiguous :class:`DataGap` ranges.
    """
    if range_start > range_end:
        raise ValueError("range_start must not be after range_end")
    if expected_interval <= timedelta(0):
        raise ValueError("expected_interval must be positive")

    expected: list[datetime] = []
    current = range_start
    while current <= range_end:
        expected.append(current)
        current += expected_interval

    actual = set(timestamps)
    missing = [ts for ts in expected if ts not in actual]
    if not missing:
        return []

    gaps: list[DataGap] = []
    gap_start = missing[0]
    previous = missing[0]
    for ts in missing[1:]:
        if ts - previous > expected_interval:
            gaps.append(DataGap(gap_start, previous))
            gap_start = ts
        previous = ts
    gaps.append(DataGap(gap_start, previous))
    return gaps


class HistoricalDataService:
    """Cache-first historical data loader built on a provider + repository.

    Reusable as-is by the Backtesting Engine, Demo Trading Agent, and Live
    Trading Agent: none of its behavior is specific to backtesting, only to
    "get validated historical data for X in [start, end], from cache where
    possible."
    """

    def __init__(self, provider: MarketDataProvider, repository: DataRepository) -> None:
        self._provider = provider
        self._repository = repository

    def detect_gaps(
        self,
        model_cls: type[CanonicalRecord],
        *,
        exchange: str,
        symbol: str,
        timeframe: Timeframe | None = None,
        start: datetime,
        end: datetime,
        expected_interval: timedelta,
    ) -> list[DataGap]:
        """Report missing records in the *already-cached* range, without
        touching the network. Useful for a standalone data-quality check.
        """
        cached = self._repository.read(
            model_cls, exchange=exchange, symbol=symbol, timeframe=timeframe, start=start, end=end
        )
        return find_gaps(
            [record.timestamp for record in cached],
            expected_interval=expected_interval,
            range_start=start,
            range_end=end,
        )

    def _ensure_and_fill_gaps(
        self,
        model_cls: type[RecordT],
        fetch: Callable[[datetime, datetime], list[RecordT]],
        *,
        exchange: str,
        symbol: str,
        timeframe: Timeframe | None,
        start: datetime,
        end: datetime,
        expected_interval: timedelta,
    ) -> list[RecordT]:
        gaps = self.detect_gaps(
            model_cls,
            exchange=exchange,
            symbol=symbol,
            timeframe=timeframe,
            start=start,
            end=end,
            expected_interval=expected_interval,
        )
        for gap in gaps:
            logger.info(
                "fetching missing range from provider",
                extra={
                    "record_type": model_cls.__name__,
                    "exchange": exchange,
                    "symbol": symbol,
                    "gap_start": gap.start.isoformat(),
                    "gap_end": gap.end.isoformat(),
                },
            )
            fetched = fetch(gap.start, gap.end)
            if fetched:
                self._repository.write(
                    model_cls, fetched, exchange=exchange, symbol=symbol, timeframe=timeframe
                )
            else:
                logger.warning(
                    "provider returned no data for a detected gap",
                    extra={
                        "record_type": model_cls.__name__,
                        "exchange": exchange,
                        "symbol": symbol,
                        "gap_start": gap.start.isoformat(),
                        "gap_end": gap.end.isoformat(),
                    },
                )
        return self._repository.read(
            model_cls, exchange=exchange, symbol=symbol, timeframe=timeframe, start=start, end=end
        )

    def ensure_ohlcv(
        self, *, exchange: str, symbol: str, timeframe: Timeframe, start: datetime, end: datetime
    ) -> list[Candle]:
        return self._ensure_and_fill_gaps(
            Candle,
            lambda gap_start, gap_end: self._provider.get_ohlcv(
                exchange=exchange, symbol=symbol, timeframe=timeframe, start=gap_start, end=gap_end
            ),
            exchange=exchange,
            symbol=symbol,
            timeframe=timeframe,
            start=start,
            end=end,
            expected_interval=timeframe.duration,
        )

    def ensure_funding_rate(
        self, *, exchange: str, symbol: str, timeframe: Timeframe, start: datetime, end: datetime
    ) -> list[FundingRate]:
        return self._ensure_and_fill_gaps(
            FundingRate,
            lambda gap_start, gap_end: self._provider.get_funding_rate(
                exchange=exchange, symbol=symbol, timeframe=timeframe, start=gap_start, end=gap_end
            ),
            exchange=exchange,
            symbol=symbol,
            timeframe=timeframe,
            start=start,
            end=end,
            expected_interval=timeframe.duration,
        )

    def ensure_open_interest(
        self, *, exchange: str, symbol: str, timeframe: Timeframe, start: datetime, end: datetime
    ) -> list[OpenInterest]:
        return self._ensure_and_fill_gaps(
            OpenInterest,
            lambda gap_start, gap_end: self._provider.get_open_interest(
                exchange=exchange, symbol=symbol, timeframe=timeframe, start=gap_start, end=gap_end
            ),
            exchange=exchange,
            symbol=symbol,
            timeframe=timeframe,
            start=start,
            end=end,
            expected_interval=timeframe.duration,
        )

    def ensure_liquidations(
        self, *, exchange: str, symbol: str, timeframe: Timeframe, start: datetime, end: datetime
    ) -> list[Liquidation]:
        return self._ensure_and_fill_gaps(
            Liquidation,
            lambda gap_start, gap_end: self._provider.get_liquidations(
                exchange=exchange, symbol=symbol, timeframe=timeframe, start=gap_start, end=gap_end
            ),
            exchange=exchange,
            symbol=symbol,
            timeframe=timeframe,
            start=start,
            end=end,
            expected_interval=timeframe.duration,
        )

    def ensure_long_short_ratio(
        self, *, exchange: str, symbol: str, timeframe: Timeframe, start: datetime, end: datetime
    ) -> list[LongShortRatio]:
        return self._ensure_and_fill_gaps(
            LongShortRatio,
            lambda gap_start, gap_end: self._provider.get_long_short_ratio(
                exchange=exchange, symbol=symbol, timeframe=timeframe, start=gap_start, end=gap_end
            ),
            exchange=exchange,
            symbol=symbol,
            timeframe=timeframe,
            start=start,
            end=end,
            expected_interval=timeframe.duration,
        )
