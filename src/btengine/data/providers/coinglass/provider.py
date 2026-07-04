"""CoinGlass implementation of the :class:`MarketDataProvider` interface.

Composes the low-level client, endpoint constants, plan-limit validation,
and the mapper. This is the only class application code should construct
directly (via :func:`build_coinglass_provider`) to get CoinGlass-backed
market data — the client, mapper, pagination, and plan-restriction details
are all implementation details of this module.

Two behaviors here exist specifically because of how CoinGlass's API works,
not out of caution:

- **Pagination**: every history endpoint caps a single response at
  :data:`endpoints.MAX_ROWS_PER_REQUEST` rows. A wide date range is fetched
  by repeatedly advancing ``start_time`` until the full range is covered —
  otherwise a large request would silently return only its first page,
  which is exactly the kind of missing-data bug this integration is meant
  to prevent.
- **Plan validation**: the account is on the Startup plan, which only
  grants certain intervals and a bounded history length per interval (see
  :mod:`plan_limits`). Requests outside those bounds are rejected before
  any HTTP call, with a clear reason, instead of surfacing as a confusing
  CoinGlass error after the fact.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from btengine.data.base import MarketDataProvider
from btengine.data.errors import InvalidResponseError
from btengine.data.providers.coinglass import endpoints, plan_limits
from btengine.data.providers.coinglass.auth import CoinGlassAuthProvider
from btengine.data.providers.coinglass.client import CoinGlassClient
from btengine.data.providers.coinglass.config import CoinGlassSettings, load_coinglass_settings
from btengine.data.providers.coinglass.mapper import (
    map_candles,
    map_funding_rates,
    map_liquidations,
    map_long_short_ratios,
    map_open_interest,
    map_supported_markets,
)
from btengine.data.providers.coinglass.rate_limiter import TokenBucketRateLimiter
from btengine.data.providers.coinglass.retry import RetryPolicy
from btengine.data.schema import (
    Candle,
    FundingRate,
    Liquidation,
    LongShortRatio,
    OpenInterest,
    SupportedMarket,
    Timeframe,
)


def _to_epoch_ms(value: datetime) -> int:
    return int(value.timestamp() * 1000)


def _from_epoch_ms(value: int) -> datetime:
    return datetime.fromtimestamp(value / 1000, tz=timezone.utc)


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

    def verify_connection(self) -> None:
        """Confirm the configured API key can reach CoinGlass. Raises on failure."""
        self._client.verify_connection()

    def get_supported_markets(self) -> list[SupportedMarket]:
        """List every exchange/instrument pair CoinGlass can supply data for."""
        raw = self._client.get(endpoints.SUPPORTED_EXCHANGE_PAIRS)
        return map_supported_markets(raw, endpoint=endpoints.SUPPORTED_EXCHANGE_PAIRS)

    # --- MarketDataProvider interface -------------------------------------

    def get_ohlcv(
        self, *, exchange: str, symbol: str, timeframe: Timeframe, start: datetime, end: datetime
    ) -> list[Candle]:
        plan_limits.validate_request(timeframe, start, end)
        raw = self._paginated_get(
            endpoints.PRICE_OHLC_HISTORY,
            {"exchange": exchange, "symbol": symbol, "interval": timeframe.value},
            start=start,
            end=end,
        )
        return map_candles(
            raw, exchange=exchange, symbol=symbol, timeframe=timeframe, endpoint=endpoints.PRICE_OHLC_HISTORY
        )

    def get_funding_rate(
        self, *, exchange: str, symbol: str, timeframe: Timeframe, start: datetime, end: datetime
    ) -> list[FundingRate]:
        plan_limits.validate_request(timeframe, start, end)
        raw = self._paginated_get(
            endpoints.FUNDING_RATE_HISTORY,
            {"exchange": exchange, "symbol": symbol, "interval": timeframe.value},
            start=start,
            end=end,
        )
        return map_funding_rates(raw, exchange=exchange, symbol=symbol, endpoint=endpoints.FUNDING_RATE_HISTORY)

    def get_open_interest(
        self, *, exchange: str, symbol: str, timeframe: Timeframe, start: datetime, end: datetime
    ) -> list[OpenInterest]:
        plan_limits.validate_request(timeframe, start, end)
        raw = self._paginated_get(
            endpoints.OPEN_INTEREST_HISTORY,
            {"exchange": exchange, "symbol": symbol, "interval": timeframe.value, "unit": "usd"},
            start=start,
            end=end,
        )
        return map_open_interest(raw, exchange=exchange, symbol=symbol, endpoint=endpoints.OPEN_INTEREST_HISTORY)

    def get_liquidations(
        self, *, exchange: str, symbol: str, timeframe: Timeframe, start: datetime, end: datetime
    ) -> list[Liquidation]:
        plan_limits.validate_request(timeframe, start, end)
        raw = self._paginated_get(
            endpoints.LIQUIDATION_HISTORY,
            {"exchange": exchange, "symbol": symbol, "interval": timeframe.value},
            start=start,
            end=end,
        )
        return map_liquidations(raw, exchange=exchange, symbol=symbol, endpoint=endpoints.LIQUIDATION_HISTORY)

    def get_long_short_ratio(
        self, *, exchange: str, symbol: str, timeframe: Timeframe, start: datetime, end: datetime
    ) -> list[LongShortRatio]:
        plan_limits.validate_request(timeframe, start, end)
        raw = self._paginated_get(
            endpoints.GLOBAL_LONG_SHORT_ACCOUNT_RATIO_HISTORY,
            {"exchange": exchange, "symbol": symbol, "interval": timeframe.value},
            start=start,
            end=end,
        )
        return map_long_short_ratios(
            raw,
            exchange=exchange,
            symbol=symbol,
            endpoint=endpoints.GLOBAL_LONG_SHORT_ACCOUNT_RATIO_HISTORY,
            long_field="global_account_long_percent",
            short_field="global_account_short_percent",
        )

    # --- CoinGlass-specific extensions (beyond the portable ABC) ----------
    # These give access to additional Startup-plan endpoints that don't have
    # a distinct canonical schema of their own: OI-weighted funding rate and
    # aggregated open interest reuse FundingRate/OpenInterest (same OHLC
    # shape, different source); top-trader ratios reuse LongShortRatio.

    def get_funding_rate_oi_weighted(
        self, *, symbol: str, timeframe: Timeframe, start: datetime, end: datetime
    ) -> list[FundingRate]:
        plan_limits.validate_request(timeframe, start, end)
        raw = self._paginated_get(
            endpoints.FUNDING_RATE_OI_WEIGHT_HISTORY,
            {"symbol": symbol, "interval": timeframe.value},
            start=start,
            end=end,
        )
        return map_funding_rates(
            raw, exchange="AGGREGATED", symbol=symbol, endpoint=endpoints.FUNDING_RATE_OI_WEIGHT_HISTORY
        )

    def get_open_interest_aggregated(
        self, *, symbol: str, timeframe: Timeframe, start: datetime, end: datetime
    ) -> list[OpenInterest]:
        plan_limits.validate_request(timeframe, start, end)
        raw = self._paginated_get(
            endpoints.OPEN_INTEREST_AGGREGATED_HISTORY,
            {"symbol": symbol, "interval": timeframe.value, "unit": "usd"},
            start=start,
            end=end,
        )
        return map_open_interest(
            raw, exchange="AGGREGATED", symbol=symbol, endpoint=endpoints.OPEN_INTEREST_AGGREGATED_HISTORY
        )

    def get_top_long_short_account_ratio(
        self, *, exchange: str, symbol: str, timeframe: Timeframe, start: datetime, end: datetime
    ) -> list[LongShortRatio]:
        plan_limits.validate_request(timeframe, start, end)
        raw = self._paginated_get(
            endpoints.TOP_LONG_SHORT_ACCOUNT_RATIO_HISTORY,
            {"exchange": exchange, "symbol": symbol, "interval": timeframe.value},
            start=start,
            end=end,
        )
        return map_long_short_ratios(
            raw,
            exchange=exchange,
            symbol=symbol,
            endpoint=endpoints.TOP_LONG_SHORT_ACCOUNT_RATIO_HISTORY,
            long_field="top_account_long_percent",
            short_field="top_account_short_percent",
        )

    def get_top_long_short_position_ratio(
        self, *, exchange: str, symbol: str, timeframe: Timeframe, start: datetime, end: datetime
    ) -> list[LongShortRatio]:
        plan_limits.validate_request(timeframe, start, end)
        raw = self._paginated_get(
            endpoints.TOP_LONG_SHORT_POSITION_RATIO_HISTORY,
            {"exchange": exchange, "symbol": symbol, "interval": timeframe.value},
            start=start,
            end=end,
        )
        return map_long_short_ratios(
            raw,
            exchange=exchange,
            symbol=symbol,
            endpoint=endpoints.TOP_LONG_SHORT_POSITION_RATIO_HISTORY,
            long_field="top_position_long_percent",
            short_field="top_position_short_percent",
        )

    # --- Pagination --------------------------------------------------------

    def _paginated_get(
        self, endpoint: str, base_params: dict[str, Any], *, start: datetime, end: datetime
    ) -> list[dict[str, Any]]:
        """Fetch every row in ``[start, end]``, paging by advancing ``start_time``.

        Stops when a page comes back with fewer than
        :data:`endpoints.MAX_ROWS_PER_REQUEST` rows (no more data) or when
        ``start_time`` reaches ``end``. A bounded iteration count guards
        against ever looping forever on a malformed/non-advancing response.
        """
        all_records: list[dict[str, Any]] = []
        current_start = start
        max_pages = 10_000

        for _ in range(max_pages):
            if current_start > end:
                break
            params = {
                **base_params,
                "start_time": _to_epoch_ms(current_start),
                "end_time": _to_epoch_ms(end),
                "limit": endpoints.MAX_ROWS_PER_REQUEST,
            }
            page = self._client.get(endpoint, params=params)
            if not isinstance(page, list):
                raise InvalidResponseError(
                    f"Expected a list payload from {endpoint}, got {type(page).__name__}",
                    endpoint=endpoint,
                    payload_excerpt=str(page)[:500],
                )
            if not page:
                break

            all_records.extend(page)
            if len(page) < endpoints.MAX_ROWS_PER_REQUEST:
                break

            last_time = page[-1].get("time") if isinstance(page[-1], dict) else None
            if last_time is None:
                break
            next_start = _from_epoch_ms(int(last_time)) + timedelta(milliseconds=1)
            if next_start <= current_start:
                break  # guard against a response that never advances
            current_start = next_start
        else:
            raise InvalidResponseError(
                f"Pagination for {endpoint} did not terminate after {max_pages} pages",
                endpoint=endpoint,
            )

        return all_records


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
