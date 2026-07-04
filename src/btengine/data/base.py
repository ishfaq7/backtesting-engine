"""Provider-agnostic market data interface.

Every concrete data provider (CoinGlass today, others later) implements
this interface and returns only canonical schema types
(:mod:`btengine.data.schema`). Nothing outside
``btengine.data.providers.*`` should depend on a specific provider's
client, mapper, or response shape.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime

from btengine.data.schema import (
    Candle,
    FundingRate,
    Liquidation,
    LongShortRatio,
    OpenInterest,
    Timeframe,
)


class MarketDataProvider(ABC):
    """Abstract contract for a historical market data source."""

    @abstractmethod
    def get_ohlcv(
        self,
        *,
        exchange: str,
        symbol: str,
        timeframe: Timeframe,
        start: datetime,
        end: datetime,
    ) -> list[Candle]:
        """Return OHLCV candles for ``symbol`` on ``exchange`` in ``[start, end]``."""

    @abstractmethod
    def get_funding_rate(
        self, *, exchange: str, symbol: str, timeframe: Timeframe, start: datetime, end: datetime
    ) -> list[FundingRate]:
        """Return funding rate history for ``symbol`` on ``exchange`` in ``[start, end]``."""

    @abstractmethod
    def get_open_interest(
        self, *, exchange: str, symbol: str, timeframe: Timeframe, start: datetime, end: datetime
    ) -> list[OpenInterest]:
        """Return open interest history for ``symbol`` on ``exchange`` in ``[start, end]``."""

    @abstractmethod
    def get_liquidations(
        self, *, exchange: str, symbol: str, timeframe: Timeframe, start: datetime, end: datetime
    ) -> list[Liquidation]:
        """Return liquidation history for ``symbol`` on ``exchange`` in ``[start, end]``."""

    @abstractmethod
    def get_long_short_ratio(
        self, *, exchange: str, symbol: str, timeframe: Timeframe, start: datetime, end: datetime
    ) -> list[LongShortRatio]:
        """Return long/short account ratio history for ``symbol`` on ``exchange``."""
