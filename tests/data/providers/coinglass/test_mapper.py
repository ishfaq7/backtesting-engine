import pytest

from btengine.data.errors import InvalidResponseError, NormalizationError
from btengine.data.providers.coinglass.mapper import (
    map_candles,
    map_funding_rates,
    map_liquidations,
    map_long_short_ratios,
    map_open_interest,
    map_supported_markets,
)
from btengine.data.schema import Timeframe

ENDPOINT = "/api/futures/price/history"
TS_MS = 1704067200000  # 2024-01-01T00:00:00Z


def test_map_candles_happy_path() -> None:
    raw = [{"time": TS_MS, "open": 100, "high": 110, "low": 90, "close": 105, "volume_usd": 12.5}]
    candles = map_candles(raw, exchange="binance", symbol="btcusdt", timeframe=Timeframe.HOUR_1, endpoint=ENDPOINT)
    assert len(candles) == 1
    assert candles[0].close == 105
    assert candles[0].volume == 12.5
    assert candles[0].timeframe == Timeframe.HOUR_1
    assert candles[0].timestamp.year == 2024


def test_map_candles_missing_field_raises_invalid_response_error() -> None:
    raw = [{"time": TS_MS, "open": 100, "high": 110, "low": 90}]  # missing close, volume_usd
    with pytest.raises(InvalidResponseError):
        map_candles(raw, exchange="binance", symbol="btcusdt", timeframe=Timeframe.HOUR_1, endpoint=ENDPOINT)


def test_map_candles_inconsistent_ohlc_raises_normalization_error() -> None:
    raw = [{"time": TS_MS, "open": 100, "high": 90, "low": 80, "close": 95, "volume_usd": 1}]
    with pytest.raises(NormalizationError):
        map_candles(raw, exchange="binance", symbol="btcusdt", timeframe=Timeframe.HOUR_1, endpoint=ENDPOINT)


def test_map_candles_bad_timestamp_raises_normalization_error() -> None:
    raw = [{"time": "not-a-timestamp", "open": 1, "high": 2, "low": 1, "close": 1.5, "volume_usd": 1}]
    with pytest.raises(NormalizationError):
        map_candles(raw, exchange="binance", symbol="btcusdt", timeframe=Timeframe.HOUR_1, endpoint=ENDPOINT)


def test_map_candles_rejects_non_list_payload() -> None:
    with pytest.raises(InvalidResponseError):
        map_candles({"not": "a list"}, exchange="binance", symbol="btcusdt", timeframe=Timeframe.HOUR_1, endpoint=ENDPOINT)


def test_map_funding_rates_uses_ohlc_close_as_the_rate() -> None:
    raw = [{"time": TS_MS, "open": 0.0001, "high": 0.0003, "low": 0.00005, "close": 0.0002}]
    results = map_funding_rates(raw, exchange="binance", symbol="btcusdt", endpoint=ENDPOINT)
    assert results[0].funding_rate == 0.0002


def test_map_funding_rates_missing_close_raises_invalid_response_error() -> None:
    raw = [{"time": TS_MS, "open": 0.0001}]
    with pytest.raises(InvalidResponseError):
        map_funding_rates(raw, exchange="binance", symbol="btcusdt", endpoint=ENDPOINT)


def test_map_open_interest_happy_path_sets_both_quantity_and_usd_fields() -> None:
    raw = [{"time": TS_MS, "open": 900, "high": 1100, "low": 800, "close": 1000}]
    results = map_open_interest(raw, exchange="binance", symbol="btcusdt", endpoint=ENDPOINT)
    assert results[0].open_interest == 1000
    assert results[0].open_interest_value_usd == 1000


def test_map_liquidations_happy_path() -> None:
    raw = [{"time": TS_MS, "long_liquidation_usd": 100000, "short_liquidation_usd": 50000}]
    results = map_liquidations(raw, exchange="binance", symbol="btcusdt", endpoint=ENDPOINT)
    assert results[0].long_liquidation_usd == 100000
    assert results[0].short_liquidation_usd == 50000


def test_map_long_short_ratios_fraction_input_passes_through() -> None:
    raw = [{"time": TS_MS, "global_account_long_percent": 0.55, "global_account_short_percent": 0.45}]
    results = map_long_short_ratios(
        raw, exchange="binance", symbol="btcusdt", endpoint=ENDPOINT,
        long_field="global_account_long_percent", short_field="global_account_short_percent",
    )
    assert results[0].long_account_ratio == pytest.approx(0.55)
    assert results[0].short_account_ratio == pytest.approx(0.45)


def test_map_long_short_ratios_percentage_input_is_normalized() -> None:
    raw = [{"time": TS_MS, "global_account_long_percent": 55, "global_account_short_percent": 45}]
    results = map_long_short_ratios(
        raw, exchange="binance", symbol="btcusdt", endpoint=ENDPOINT,
        long_field="global_account_long_percent", short_field="global_account_short_percent",
    )
    assert results[0].long_account_ratio == pytest.approx(0.55)
    assert results[0].short_account_ratio == pytest.approx(0.45)


def test_map_long_short_ratios_supports_top_trader_field_names() -> None:
    raw = [{"time": TS_MS, "top_position_long_percent": 0.6, "top_position_short_percent": 0.4}]
    results = map_long_short_ratios(
        raw, exchange="binance", symbol="btcusdt", endpoint=ENDPOINT,
        long_field="top_position_long_percent", short_field="top_position_short_percent",
    )
    assert results[0].long_account_ratio == pytest.approx(0.6)


def test_map_funding_rates_invalid_canonical_fields_raise_normalization_error() -> None:
    raw = [{"time": TS_MS, "close": 0.0001}]
    with pytest.raises(NormalizationError):
        map_funding_rates(raw, exchange="   ", symbol="btcusdt", endpoint=ENDPOINT)


def test_map_open_interest_invalid_canonical_fields_raise_normalization_error() -> None:
    raw = [{"time": TS_MS, "close": 1000}]
    with pytest.raises(NormalizationError):
        map_open_interest(raw, exchange="   ", symbol="btcusdt", endpoint=ENDPOINT)


def test_map_liquidations_invalid_canonical_fields_raise_normalization_error() -> None:
    raw = [{"time": TS_MS, "long_liquidation_usd": 1, "short_liquidation_usd": 2}]
    with pytest.raises(NormalizationError):
        map_liquidations(raw, exchange="   ", symbol="btcusdt", endpoint=ENDPOINT)


def test_map_long_short_ratios_invalid_canonical_fields_raise_normalization_error() -> None:
    raw = [{"time": TS_MS, "global_account_long_percent": 0.5, "global_account_short_percent": 0.5}]
    with pytest.raises(NormalizationError):
        map_long_short_ratios(
            raw, exchange="   ", symbol="btcusdt", endpoint=ENDPOINT,
            long_field="global_account_long_percent", short_field="global_account_short_percent",
        )


# --- map_supported_markets --------------------------------------------------


def test_map_supported_markets_happy_path() -> None:
    raw = {
        "Binance": [{"instrument_id": "BTCUSDT_PERP", "base_asset": "BTC", "quote_asset": "USDT"}],
        "Bitget": [{"instrument_id": "ETHUSDT_UMCBL", "base_asset": "ETH", "quote_asset": "USDT"}],
    }
    markets = map_supported_markets(raw, endpoint=ENDPOINT)
    assert len(markets) == 2
    by_exchange = {m.exchange: m for m in markets}
    assert by_exchange["BINANCE"].instrument_id == "BTCUSDT_PERP"
    assert by_exchange["BITGET"].base_asset == "ETH"


def test_map_supported_markets_rejects_non_dict_payload() -> None:
    with pytest.raises(InvalidResponseError):
        map_supported_markets([{"not": "a dict"}], endpoint=ENDPOINT)


def test_map_supported_markets_rejects_non_list_exchange_value() -> None:
    with pytest.raises(InvalidResponseError):
        map_supported_markets({"Binance": "not-a-list"}, endpoint=ENDPOINT)


def test_map_supported_markets_rejects_non_dict_pair_entry() -> None:
    with pytest.raises(InvalidResponseError):
        map_supported_markets({"Binance": ["not-a-dict"]}, endpoint=ENDPOINT)


def test_map_supported_markets_missing_field_raises_invalid_response_error() -> None:
    raw = {"Binance": [{"instrument_id": "BTCUSDT_PERP", "base_asset": "BTC"}]}  # missing quote_asset
    with pytest.raises(InvalidResponseError):
        map_supported_markets(raw, endpoint=ENDPOINT)


def test_map_supported_markets_invalid_canonical_fields_raise_normalization_error() -> None:
    raw = {"Binance": [{"instrument_id": "   ", "base_asset": "BTC", "quote_asset": "USDT"}]}
    with pytest.raises(NormalizationError):
        map_supported_markets(raw, endpoint=ENDPOINT)
