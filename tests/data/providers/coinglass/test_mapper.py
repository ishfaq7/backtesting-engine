import pytest

from btengine.data.errors import InvalidResponseError, NormalizationError
from btengine.data.providers.coinglass.mapper import (
    map_candles,
    map_funding_rates,
    map_liquidations,
    map_long_short_ratios,
    map_open_interest,
)
from btengine.data.schema import Timeframe

ENDPOINT = "/api/futures/price/history"
TS_MS = 1704067200000  # 2024-01-01T00:00:00Z


def test_map_candles_happy_path() -> None:
    raw = [{"time": TS_MS, "open": 100, "high": 110, "low": 90, "close": 105, "volume": 12.5}]
    candles = map_candles(raw, exchange="binance", symbol="btcusdt", timeframe=Timeframe.HOUR_1, endpoint=ENDPOINT)
    assert len(candles) == 1
    assert candles[0].close == 105
    assert candles[0].timeframe == Timeframe.HOUR_1
    assert candles[0].timestamp.year == 2024


def test_map_candles_missing_field_raises_invalid_response_error() -> None:
    raw = [{"time": TS_MS, "open": 100, "high": 110, "low": 90}]  # missing close, volume
    with pytest.raises(InvalidResponseError):
        map_candles(raw, exchange="binance", symbol="btcusdt", timeframe=Timeframe.HOUR_1, endpoint=ENDPOINT)


def test_map_candles_inconsistent_ohlc_raises_normalization_error() -> None:
    raw = [{"time": TS_MS, "open": 100, "high": 90, "low": 80, "close": 95, "volume": 1}]
    with pytest.raises(NormalizationError):
        map_candles(raw, exchange="binance", symbol="btcusdt", timeframe=Timeframe.HOUR_1, endpoint=ENDPOINT)


def test_map_candles_bad_timestamp_raises_normalization_error() -> None:
    raw = [{"time": "not-a-timestamp", "open": 1, "high": 2, "low": 1, "close": 1.5, "volume": 1}]
    with pytest.raises(NormalizationError):
        map_candles(raw, exchange="binance", symbol="btcusdt", timeframe=Timeframe.HOUR_1, endpoint=ENDPOINT)


def test_map_candles_rejects_non_list_payload() -> None:
    with pytest.raises(InvalidResponseError):
        map_candles({"not": "a list"}, exchange="binance", symbol="btcusdt", timeframe=Timeframe.HOUR_1, endpoint=ENDPOINT)


def test_map_funding_rates_happy_path_with_optional_field() -> None:
    raw = [{"time": TS_MS, "fundingRate": 0.0001, "predictedFundingRate": 0.0002}]
    results = map_funding_rates(raw, exchange="binance", symbol="btcusdt", endpoint=ENDPOINT)
    assert results[0].funding_rate == 0.0001
    assert results[0].predicted_funding_rate == 0.0002


def test_map_funding_rates_optional_field_absent() -> None:
    raw = [{"time": TS_MS, "fundingRate": 0.0001}]
    results = map_funding_rates(raw, exchange="binance", symbol="btcusdt", endpoint=ENDPOINT)
    assert results[0].predicted_funding_rate is None


def test_map_open_interest_happy_path() -> None:
    raw = [{"time": TS_MS, "openInterest": 1000, "openInterestValue": 50000000}]
    results = map_open_interest(raw, exchange="binance", symbol="btcusdt", endpoint=ENDPOINT)
    assert results[0].open_interest == 1000
    assert results[0].open_interest_value_usd == 50000000


def test_map_liquidations_happy_path() -> None:
    raw = [{"time": TS_MS, "longVolUsd": 100000, "shortVolUsd": 50000}]
    results = map_liquidations(raw, exchange="binance", symbol="btcusdt", endpoint=ENDPOINT)
    assert results[0].long_liquidation_usd == 100000
    assert results[0].short_liquidation_usd == 50000


def test_map_long_short_ratios_fraction_input_passes_through() -> None:
    raw = [{"time": TS_MS, "longAccount": 0.55, "shortAccount": 0.45}]
    results = map_long_short_ratios(raw, exchange="binance", symbol="btcusdt", endpoint=ENDPOINT)
    assert results[0].long_account_ratio == pytest.approx(0.55)
    assert results[0].short_account_ratio == pytest.approx(0.45)


def test_map_long_short_ratios_percentage_input_is_normalized() -> None:
    raw = [{"time": TS_MS, "longAccount": 55, "shortAccount": 45}]
    results = map_long_short_ratios(raw, exchange="binance", symbol="btcusdt", endpoint=ENDPOINT)
    assert results[0].long_account_ratio == pytest.approx(0.55)
    assert results[0].short_account_ratio == pytest.approx(0.45)


def test_map_funding_rates_invalid_canonical_fields_raise_normalization_error() -> None:
    raw = [{"time": TS_MS, "fundingRate": 0.0001}]
    with pytest.raises(NormalizationError):
        map_funding_rates(raw, exchange="   ", symbol="btcusdt", endpoint=ENDPOINT)


def test_map_open_interest_invalid_canonical_fields_raise_normalization_error() -> None:
    raw = [{"time": TS_MS, "openInterest": 1000}]
    with pytest.raises(NormalizationError):
        map_open_interest(raw, exchange="   ", symbol="btcusdt", endpoint=ENDPOINT)


def test_map_liquidations_invalid_canonical_fields_raise_normalization_error() -> None:
    raw = [{"time": TS_MS, "longVolUsd": 1, "shortVolUsd": 2}]
    with pytest.raises(NormalizationError):
        map_liquidations(raw, exchange="   ", symbol="btcusdt", endpoint=ENDPOINT)


def test_map_long_short_ratios_invalid_canonical_fields_raise_normalization_error() -> None:
    raw = [{"time": TS_MS, "longAccount": 0.5, "shortAccount": 0.5}]
    with pytest.raises(NormalizationError):
        map_long_short_ratios(raw, exchange="   ", symbol="btcusdt", endpoint=ENDPOINT)
