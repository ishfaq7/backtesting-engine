from datetime import datetime, timezone
from typing import Any, Mapping

import pytest

from btengine.data.base import MarketDataProvider
from btengine.data.providers.coinglass import endpoints
from btengine.data.providers.coinglass.provider import CoinGlassDataProvider, build_coinglass_provider
from btengine.data.schema import Timeframe

UTC = timezone.utc
TS_MS = 1704067200000  # 2024-01-01T00:00:00Z


class SpyClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, Mapping[str, Any]]] = []
        self.next_response: Any = []
        self.closed = False

    def get(self, endpoint: str, params: Mapping[str, Any] | None = None) -> Any:
        self.calls.append((endpoint, dict(params or {})))
        return self.next_response

    def close(self) -> None:
        self.closed = True


@pytest.fixture
def spy_client() -> SpyClient:
    return SpyClient()


def test_is_a_market_data_provider(spy_client: SpyClient) -> None:
    provider = CoinGlassDataProvider(spy_client)  # type: ignore[arg-type]
    assert isinstance(provider, MarketDataProvider)


def test_get_ohlcv_calls_correct_endpoint_with_expected_params(spy_client: SpyClient) -> None:
    spy_client.next_response = [{"time": TS_MS, "open": 1, "high": 2, "low": 1, "close": 1.5, "volume": 10}]
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
    assert params["startTime"] == int(start.timestamp() * 1000)
    assert params["endTime"] == int(end.timestamp() * 1000)


def test_get_funding_rate_calls_correct_endpoint(spy_client: SpyClient) -> None:
    spy_client.next_response = [{"time": TS_MS, "fundingRate": 0.0001}]
    provider = CoinGlassDataProvider(spy_client)  # type: ignore[arg-type]

    result = provider.get_funding_rate(
        exchange="binance", symbol="btcusdt", start=datetime(2024, 1, 1, tzinfo=UTC), end=datetime(2024, 1, 2, tzinfo=UTC)
    )
    assert len(result) == 1
    assert spy_client.calls[0][0] == endpoints.FUNDING_RATE_OHLC_HISTORY


def test_get_open_interest_calls_correct_endpoint(spy_client: SpyClient) -> None:
    spy_client.next_response = [{"time": TS_MS, "openInterest": 1000}]
    provider = CoinGlassDataProvider(spy_client)  # type: ignore[arg-type]
    result = provider.get_open_interest(
        exchange="binance", symbol="btcusdt", start=datetime(2024, 1, 1, tzinfo=UTC), end=datetime(2024, 1, 2, tzinfo=UTC)
    )
    assert len(result) == 1
    assert spy_client.calls[0][0] == endpoints.OPEN_INTEREST_OHLC_HISTORY


def test_get_liquidations_calls_correct_endpoint(spy_client: SpyClient) -> None:
    spy_client.next_response = [{"time": TS_MS, "longVolUsd": 1, "shortVolUsd": 2}]
    provider = CoinGlassDataProvider(spy_client)  # type: ignore[arg-type]
    result = provider.get_liquidations(
        exchange="binance", symbol="btcusdt", start=datetime(2024, 1, 1, tzinfo=UTC), end=datetime(2024, 1, 2, tzinfo=UTC)
    )
    assert len(result) == 1
    assert spy_client.calls[0][0] == endpoints.LIQUIDATION_HISTORY


def test_get_long_short_ratio_calls_correct_endpoint(spy_client: SpyClient) -> None:
    spy_client.next_response = [{"time": TS_MS, "longAccount": 0.5, "shortAccount": 0.5}]
    provider = CoinGlassDataProvider(spy_client)  # type: ignore[arg-type]
    result = provider.get_long_short_ratio(
        exchange="binance", symbol="btcusdt", start=datetime(2024, 1, 1, tzinfo=UTC), end=datetime(2024, 1, 2, tzinfo=UTC)
    )
    assert len(result) == 1
    assert spy_client.calls[0][0] == endpoints.LONG_SHORT_RATIO_HISTORY


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
