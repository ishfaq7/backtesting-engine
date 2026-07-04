"""CoinGlass implementation of the :class:`MarketDataProvider` interface.

Composes the low-level client and the mapper functions. This is the only
class application code should construct directly (via
:func:`build_coinglass_provider`) to get CoinGlass-backed market data — the
client, mapper, and endpoint constants are implementation details of this
module.
"""

from __future__ import annotations

from datetime import datetime

from btengine.data.base import MarketDataProvider
from btengine.data.providers.coinglass import endpoints
from btengine.data.providers.coinglass.auth import CoinGlassAuthProvider
from btengine.data.providers.coinglass.client import CoinGlassClient
from btengine.data.providers.coinglass.config import CoinGlassSettings, load_coinglass_settings
from btengine.data.providers.coinglass.mapper import (
    map_candles,
    map_funding_rates,
    map_liquidations,
    map_long_short_ratios,
    map_open_interest,
)
from btengine.data.providers.coinglass.rate_limiter import TokenBucketRateLimiter
from btengine.data.providers.coinglass.retry import RetryPolicy
from btengine.data.schema import (
    Candle,
    FundingRate,
    Liquidation,
    LongShortRatio,
    OpenInterest,
    Timeframe,
)


def _to_epoch_ms(value: datetime) -> int:
    return int(value.timestamp() * 1000)


class CoinGlassDataProvider(MarketDataProvider):
    """Fetches historical market data from CoinGlass and returns canonical models."""

    def __init__(self, client: CoinGlassClient) -> None:
        self._client = client

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "CoinGlassDataProvider":
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    def get_ohlcv(
        self, *, exchange: str, symbol: str, timeframe: Timeframe, start: datetime, end: datetime
    ) -> list[Candle]:
        raw = self._client.get(
            endpoints.PRICE_OHLC_HISTORY,
            params={
                "exchange": exchange,
                "symbol": symbol,
                "interval": timeframe.value,
                "startTime": _to_epoch_ms(start),
                "endTime": _to_epoch_ms(end),
            },
        )
        return map_candles(
            raw,
            exchange=exchange,
            symbol=symbol,
            timeframe=timeframe,
            endpoint=endpoints.PRICE_OHLC_HISTORY,
        )

    def get_funding_rate(
        self, *, exchange: str, symbol: str, start: datetime, end: datetime
    ) -> list[FundingRate]:
        raw = self._client.get(
            endpoints.FUNDING_RATE_OHLC_HISTORY,
            params={
                "exchange": exchange,
                "symbol": symbol,
                "startTime": _to_epoch_ms(start),
                "endTime": _to_epoch_ms(end),
            },
        )
        return map_funding_rates(
            raw, exchange=exchange, symbol=symbol, endpoint=endpoints.FUNDING_RATE_OHLC_HISTORY
        )

    def get_open_interest(
        self, *, exchange: str, symbol: str, start: datetime, end: datetime
    ) -> list[OpenInterest]:
        raw = self._client.get(
            endpoints.OPEN_INTEREST_OHLC_HISTORY,
            params={
                "exchange": exchange,
                "symbol": symbol,
                "startTime": _to_epoch_ms(start),
                "endTime": _to_epoch_ms(end),
            },
        )
        return map_open_interest(
            raw, exchange=exchange, symbol=symbol, endpoint=endpoints.OPEN_INTEREST_OHLC_HISTORY
        )

    def get_liquidations(
        self, *, exchange: str, symbol: str, start: datetime, end: datetime
    ) -> list[Liquidation]:
        raw = self._client.get(
            endpoints.LIQUIDATION_HISTORY,
            params={
                "exchange": exchange,
                "symbol": symbol,
                "startTime": _to_epoch_ms(start),
                "endTime": _to_epoch_ms(end),
            },
        )
        return map_liquidations(
            raw, exchange=exchange, symbol=symbol, endpoint=endpoints.LIQUIDATION_HISTORY
        )

    def get_long_short_ratio(
        self, *, exchange: str, symbol: str, start: datetime, end: datetime
    ) -> list[LongShortRatio]:
        raw = self._client.get(
            endpoints.LONG_SHORT_RATIO_HISTORY,
            params={
                "exchange": exchange,
                "symbol": symbol,
                "startTime": _to_epoch_ms(start),
                "endTime": _to_epoch_ms(end),
            },
        )
        return map_long_short_ratios(
            raw, exchange=exchange, symbol=symbol, endpoint=endpoints.LONG_SHORT_RATIO_HISTORY
        )


def build_coinglass_provider(settings: CoinGlassSettings | None = None) -> CoinGlassDataProvider:
    """Composition-root factory: config -> auth -> rate limiter -> retry -> client -> provider."""
    resolved_settings = settings or load_coinglass_settings()
    auth_provider = CoinGlassAuthProvider(resolved_settings)
    rate_limiter = TokenBucketRateLimiter(
        resolved_settings.rate_limit_requests, resolved_settings.rate_limit_period_seconds
    )
    retry_policy = RetryPolicy(
        max_retries=resolved_settings.max_retries,
        base_delay_seconds=resolved_settings.backoff_base_seconds,
        max_delay_seconds=resolved_settings.backoff_max_seconds,
    )
    client = CoinGlassClient(resolved_settings, auth_provider, rate_limiter, retry_policy)
    return CoinGlassDataProvider(client)
