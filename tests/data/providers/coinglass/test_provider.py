from datetime import datetime, timedelta, timezone
from typing import Any, Mapping

import pytest

from btengine.data.base import MarketDataProvider
from btengine.data.errors import InvalidResponseError, PlanRestrictionError
from btengine.data.providers.coinglass import endpoints
from btengine.data.providers.coinglass.provider import CoinGlassDataProvider, build_coinglass_provider
from btengine.data.schema import Timeframe

UTC = timezone.utc
TS_MS = 1704067200000  # 2024-01-01T00:00:00Z


class SpyClient:
    """Fake CoinGlassClient. Returns ``responses`` in order if set (one per
    call, for pagination tests), else always returns ``next_response``.
    """

    def __init__(self) -> None:
        self.calls: list[tuple[str, Mapping[str, Any]]] = []
        self.next_response: Any = []
        self.responses: list[Any] | None = None
        self.closed = False
        self.verify_called = False

    def get(self, endpoint: str, params: Mapping[str, Any] | None = None) -> Any:
        self.calls.append((endpoint, dict(params or {})))
        if self.responses is not None:
            return self.responses.pop(0)
        return self.next_response

    def verify_connection(self) -> None:
        self.verify_called = True

    def close(self) -> None:
        self.closed = True


@pytest.fixture
def spy_client() -> SpyClient:
    return SpyClient()


def test_is_a_market_data_provider(spy_client: SpyClient) -> None:
    provider = CoinGlassDataProvider(spy_client)  # type: ignore[arg-type]
    assert isinstance(provider, MarketDataProvider)


def test_get_ohlcv_calls_correct_endpoint_with_expected_params(spy_client: SpyClient) -> None:
    spy_client.next_response = [{"time": TS_MS, "open": 1, "high": 2, "low": 1, "close": 1.5, "volume_usd": 10}]
    provider = CoinGlassDataProvider(spy_client)  # type: ignore[arg-type]

    start = datetime(2024, 1, 1, tzinfo=UTC)
    end = datetime(2024, 1, 2, tzinfo=UTC)
    result = provider.get_ohlcv(exchange="binance", symbol="btcusdt", timeframe=Timeframe.HOUR_1, start=start, end=end)

    assert len(result) == 1
    endpoint, params = spy_client.calls[0]
    assert endpoint == endpoints.PRICE_OHLC_HISTORY
    assert params["exchange"] == "binance"
    assert params["symbol"] == "btcusdt"
    assert params["interval"] == "1h"
    assert params["start_time"] == int(start.timestamp() * 1000)
    assert params["end_time"] == int(end.timestamp() * 1000)
    assert params["limit"] == endpoints.MAX_ROWS_PER_REQUEST


def test_get_ohlcv_rejects_unsupported_timeframe(spy_client: SpyClient) -> None:
    provider = CoinGlassDataProvider(spy_client)  # type: ignore[arg-type]
    with pytest.raises(PlanRestrictionError):
        provider.get_ohlcv(
            exchange="binance", symbol="btcusdt", timeframe=Timeframe.MIN_1,
            start=datetime(2024, 1, 1, tzinfo=UTC), end=datetime(2024, 1, 2, tzinfo=UTC),
        )
    assert spy_client.calls == []  # rejected before any HTTP call


def test_get_ohlcv_rejects_range_beyond_plan_history(spy_client: SpyClient) -> None:
    provider = CoinGlassDataProvider(spy_client)  # type: ignore[arg-type]
    with pytest.raises(PlanRestrictionError):
        provider.get_ohlcv(
            exchange="binance", symbol="btcusdt", timeframe=Timeframe.HOUR_1,
            start=datetime(2024, 1, 1, tzinfo=UTC), end=datetime(2024, 1, 1, tzinfo=UTC) + timedelta(days=200),
        )


def test_get_funding_rate_calls_correct_endpoint(spy_client: SpyClient) -> None:
    spy_client.next_response = [{"time": TS_MS, "open": 0.0001, "high": 0.0002, "low": 0.0001, "close": 0.00015}]
    provider = CoinGlassDataProvider(spy_client)  # type: ignore[arg-type]

    result = provider.get_funding_rate(
        exchange="binance", symbol="btcusdt", timeframe=Timeframe.HOUR_1,
        start=datetime(2024, 1, 1, tzinfo=UTC), end=datetime(2024, 1, 2, tzinfo=UTC),
    )
    assert len(result) == 1
    assert spy_client.calls[0][0] == endpoints.FUNDING_RATE_HISTORY


def test_get_open_interest_calls_correct_endpoint_and_requests_usd_unit(spy_client: SpyClient) -> None:
    spy_client.next_response = [{"time": TS_MS, "open": 900, "high": 1100, "low": 800, "close": 1000}]
    provider = CoinGlassDataProvider(spy_client)  # type: ignore[arg-type]
    result = provider.get_open_interest(
        exchange="binance", symbol="btcusdt", timeframe=Timeframe.HOUR_1,
        start=datetime(2024, 1, 1, tzinfo=UTC), end=datetime(2024, 1, 2, tzinfo=UTC),
    )
    assert len(result) == 1
    endpoint, params = spy_client.calls[0]
    assert endpoint == endpoints.OPEN_INTEREST_HISTORY
    assert params["unit"] == "usd"


def test_get_liquidations_calls_correct_endpoint(spy_client: SpyClient) -> None:
    spy_client.next_response = [{"time": TS_MS, "long_liquidation_usd": 1, "short_liquidation_usd": 2}]
    provider = CoinGlassDataProvider(spy_client)  # type: ignore[arg-type]
    result = provider.get_liquidations(
        exchange="binance", symbol="btcusdt", timeframe=Timeframe.HOUR_1,
        start=datetime(2024, 1, 1, tzinfo=UTC), end=datetime(2024, 1, 2, tzinfo=UTC),
    )
    assert len(result) == 1
    assert spy_client.calls[0][0] == endpoints.LIQUIDATION_HISTORY


def test_get_long_short_ratio_calls_correct_endpoint(spy_client: SpyClient) -> None:
    spy_client.next_response = [
        {"time": TS_MS, "global_account_long_percent": 0.5, "global_account_short_percent": 0.5}
    ]
    provider = CoinGlassDataProvider(spy_client)  # type: ignore[arg-type]
    result = provider.get_long_short_ratio(
        exchange="binance", symbol="btcusdt", timeframe=Timeframe.HOUR_1,
        start=datetime(2024, 1, 1, tzinfo=UTC), end=datetime(2024, 1, 2, tzinfo=UTC),
    )
    assert len(result) == 1
    assert spy_client.calls[0][0] == endpoints.GLOBAL_LONG_SHORT_ACCOUNT_RATIO_HISTORY


# --- CoinGlass-specific extension methods -----------------------------------


def test_get_funding_rate_oi_weighted(spy_client: SpyClient) -> None:
    spy_client.next_response = [{"time": TS_MS, "open": 0.0001, "high": 0.0002, "low": 0.0001, "close": 0.00012}]
    provider = CoinGlassDataProvider(spy_client)  # type: ignore[arg-type]
    result = provider.get_funding_rate_oi_weighted(
        symbol="btcusdt", timeframe=Timeframe.HOUR_1,
        start=datetime(2024, 1, 1, tzinfo=UTC), end=datetime(2024, 1, 2, tzinfo=UTC),
    )
    assert len(result) == 1
    assert spy_client.calls[0][0] == endpoints.FUNDING_RATE_OI_WEIGHT_HISTORY


def test_get_open_interest_aggregated(spy_client: SpyClient) -> None:
    spy_client.next_response = [{"time": TS_MS, "open": 900, "high": 1100, "low": 800, "close": 1000}]
    provider = CoinGlassDataProvider(spy_client)  # type: ignore[arg-type]
    result = provider.get_open_interest_aggregated(
        symbol="btcusdt", timeframe=Timeframe.HOUR_1,
        start=datetime(2024, 1, 1, tzinfo=UTC), end=datetime(2024, 1, 2, tzinfo=UTC),
    )
    assert len(result) == 1
    assert spy_client.calls[0][0] == endpoints.OPEN_INTEREST_AGGREGATED_HISTORY


def test_get_top_long_short_account_ratio(spy_client: SpyClient) -> None:
    spy_client.next_response = [
        {"time": TS_MS, "top_account_long_percent": 0.6, "top_account_short_percent": 0.4}
    ]
    provider = CoinGlassDataProvider(spy_client)  # type: ignore[arg-type]
    result = provider.get_top_long_short_account_ratio(
        exchange="binance", symbol="btcusdt", timeframe=Timeframe.HOUR_1,
        start=datetime(2024, 1, 1, tzinfo=UTC), end=datetime(2024, 1, 2, tzinfo=UTC),
    )
    assert len(result) == 1
    assert spy_client.calls[0][0] == endpoints.TOP_LONG_SHORT_ACCOUNT_RATIO_HISTORY


def test_get_top_long_short_position_ratio(spy_client: SpyClient) -> None:
    spy_client.next_response = [
        {"time": TS_MS, "top_position_long_percent": 0.6, "top_position_short_percent": 0.4}
    ]
    provider = CoinGlassDataProvider(spy_client)  # type: ignore[arg-type]
    result = provider.get_top_long_short_position_ratio(
        exchange="binance", symbol="btcusdt", timeframe=Timeframe.HOUR_1,
        start=datetime(2024, 1, 1, tzinfo=UTC), end=datetime(2024, 1, 2, tzinfo=UTC),
    )
    assert len(result) == 1
    assert spy_client.calls[0][0] == endpoints.TOP_LONG_SHORT_POSITION_RATIO_HISTORY


# --- Discovery / connection verification ------------------------------------


def test_verify_connection_delegates_to_client(spy_client: SpyClient) -> None:
    provider = CoinGlassDataProvider(spy_client)  # type: ignore[arg-type]
    provider.verify_connection()
    assert spy_client.verify_called is True


def test_get_supported_markets(spy_client: SpyClient) -> None:
    spy_client.next_response = {
        "Binance": [{"instrument_id": "BTCUSDT_PERP", "base_asset": "BTC", "quote_asset": "USDT"}]
    }
    provider = CoinGlassDataProvider(spy_client)  # type: ignore[arg-type]
    markets = provider.get_supported_markets()
    assert len(markets) == 1
    assert markets[0].exchange == "BINANCE"
    assert spy_client.calls[0][0] == endpoints.SUPPORTED_EXCHANGE_PAIRS


# --- Pagination --------------------------------------------------------------


def test_pagination_stops_when_page_is_smaller_than_limit(spy_client: SpyClient) -> None:
    spy_client.next_response = [
        {"time": TS_MS, "open": 1, "high": 2, "low": 1, "close": 1.5, "volume_usd": 1}
    ]
    provider = CoinGlassDataProvider(spy_client)  # type: ignore[arg-type]
    provider.get_ohlcv(
        exchange="binance", symbol="btcusdt", timeframe=Timeframe.HOUR_1,
        start=datetime(2024, 1, 1, tzinfo=UTC), end=datetime(2024, 1, 2, tzinfo=UTC),
    )
    assert len(spy_client.calls) == 1


def test_pagination_advances_start_time_across_full_pages(spy_client: SpyClient) -> None:
    full_page = [
        {
            "time": TS_MS + i * 3_600_000,
            "open": 1, "high": 2, "low": 1, "close": 1.5, "volume_usd": 1,
        }
        for i in range(endpoints.MAX_ROWS_PER_REQUEST)
    ]
    final_page = [{"time": TS_MS + endpoints.MAX_ROWS_PER_REQUEST * 3_600_000, "open": 1, "high": 2, "low": 1, "close": 1.5, "volume_usd": 1}]
    spy_client.responses = [full_page, final_page]

    provider = CoinGlassDataProvider(spy_client)  # type: ignore[arg-type]
    result = provider.get_ohlcv(
        exchange="binance", symbol="btcusdt", timeframe=Timeframe.HOUR_1,
        start=datetime(2024, 1, 1, tzinfo=UTC), end=datetime(2024, 1, 1, tzinfo=UTC) + timedelta(days=170),
    )

    assert len(spy_client.calls) == 2
    assert len(result) == endpoints.MAX_ROWS_PER_REQUEST + 1
    # second call's start_time must have advanced past the first page's last candle
    second_call_start = spy_client.calls[1][1]["start_time"]
    assert second_call_start == full_page[-1]["time"] + 1


def test_pagination_rejects_non_list_page(spy_client: SpyClient) -> None:
    spy_client.next_response = {"not": "a list"}
    provider = CoinGlassDataProvider(spy_client)  # type: ignore[arg-type]
    with pytest.raises(InvalidResponseError):
        provider.get_ohlcv(
            exchange="binance", symbol="btcusdt", timeframe=Timeframe.HOUR_1,
            start=datetime(2024, 1, 1, tzinfo=UTC), end=datetime(2024, 1, 2, tzinfo=UTC),
        )


def test_pagination_stops_on_empty_page() -> None:
    spy_client = SpyClient()
    spy_client.next_response = []
    provider = CoinGlassDataProvider(spy_client)  # type: ignore[arg-type]
    result = provider.get_ohlcv(
        exchange="binance", symbol="btcusdt", timeframe=Timeframe.HOUR_1,
        start=datetime(2024, 1, 1, tzinfo=UTC), end=datetime(2024, 1, 2, tzinfo=UTC),
    )
    assert result == []
    assert len(spy_client.calls) == 1


def test_pagination_stops_when_last_row_has_no_time_field() -> None:
    spy_client = SpyClient()
    full_page = [{"open": 1, "high": 2, "low": 1, "close": 1.5, "volume_usd": 1} for _ in range(endpoints.MAX_ROWS_PER_REQUEST)]
    spy_client.next_response = full_page
    provider = CoinGlassDataProvider(spy_client)  # type: ignore[arg-type]
    # A page whose rows have no "time" field can't tell pagination where to
    # continue from, so it must stop after this one call rather than loop.
    raw = provider._paginated_get(
        endpoints.PRICE_OHLC_HISTORY,
        {"exchange": "binance", "symbol": "btcusdt", "interval": "1h"},
        start=datetime(2024, 1, 1, tzinfo=UTC),
        end=datetime(2024, 1, 1, tzinfo=UTC) + timedelta(days=170),
    )
    assert len(spy_client.calls) == 1
    assert len(raw) == endpoints.MAX_ROWS_PER_REQUEST


def test_pagination_stops_exactly_at_end_of_range() -> None:
    spy_client = SpyClient()
    end = datetime(2024, 1, 1, tzinfo=UTC) + timedelta(hours=endpoints.MAX_ROWS_PER_REQUEST - 1)
    full_page = [
        {"time": TS_MS + i * 3_600_000, "open": 1, "high": 2, "low": 1, "close": 1.5, "volume_usd": 1}
        for i in range(endpoints.MAX_ROWS_PER_REQUEST)
    ]
    spy_client.next_response = full_page
    provider = CoinGlassDataProvider(spy_client)  # type: ignore[arg-type]
    result = provider.get_ohlcv(
        exchange="binance", symbol="btcusdt", timeframe=Timeframe.HOUR_1,
        start=datetime(2024, 1, 1, tzinfo=UTC), end=end,
    )
    # the full page exactly covers [start, end]; the next page's start_time
    # would be past end, so pagination must stop without another call.
    assert len(spy_client.calls) == 1
    assert len(result) == endpoints.MAX_ROWS_PER_REQUEST


def test_pagination_stops_when_start_time_does_not_advance(spy_client: SpyClient) -> None:
    # A full page whose last row's timestamp keeps landing at or before
    # where the *previous* page already advanced to would loop forever if
    # not guarded against. The same fixed full page is returned every call:
    # call 1 advances start_time to TS_MS+1ms; call 2's "next start" would
    # be TS_MS+1ms again (not beyond it) -> pagination must stop there
    # instead of looping forever.
    stuck_page = [
        {"time": TS_MS, "open": 1, "high": 2, "low": 1, "close": 1.5, "volume_usd": 1}
        for _ in range(endpoints.MAX_ROWS_PER_REQUEST)
    ]
    spy_client.next_response = stuck_page
    provider = CoinGlassDataProvider(spy_client)  # type: ignore[arg-type]
    result = provider.get_ohlcv(
        exchange="binance", symbol="btcusdt", timeframe=Timeframe.HOUR_1,
        start=datetime(2024, 1, 1, tzinfo=UTC), end=datetime(2024, 1, 1, tzinfo=UTC) + timedelta(days=170),
    )
    assert len(spy_client.calls) == 2
    assert len(result) == endpoints.MAX_ROWS_PER_REQUEST * 2


def test_context_manager_closes_underlying_client(spy_client: SpyClient) -> None:
    with CoinGlassDataProvider(spy_client) as provider:  # type: ignore[arg-type]
        assert isinstance(provider, CoinGlassDataProvider)
    assert spy_client.closed is True


def test_build_coinglass_provider_wires_dependencies_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COINGLASS_API_KEY", "env-key")
    provider = build_coinglass_provider()
    try:
        assert isinstance(provider, CoinGlassDataProvider)
    finally:
        provider.close()
