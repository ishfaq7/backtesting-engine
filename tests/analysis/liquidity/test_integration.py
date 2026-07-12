from datetime import datetime, timedelta, timezone

from btengine.analysis.liquidity.integration import (
    liquidation_observations_from_records,
    open_interest_observations_from_records,
    price_observations_from_candles,
    ratio_observations_from_records,
)
from btengine.data.schema import Candle, Liquidation, LongShortRatio, OpenInterest, Timeframe

UTC = timezone.utc


def _ts(hour: int) -> datetime:
    return datetime(2024, 1, 1, tzinfo=UTC) + timedelta(hours=hour)


def test_liquidation_observations_from_records_maps_fields() -> None:
    records = [
        Liquidation(exchange="binance", symbol="btcusdt", timestamp=_ts(0), long_liquidation_usd=100.0, short_liquidation_usd=50.0),
        Liquidation(exchange="binance", symbol="btcusdt", timestamp=_ts(1), long_liquidation_usd=200.0, short_liquidation_usd=60.0),
    ]
    observations = liquidation_observations_from_records(records)
    assert [o.long_liquidation_usd for o in observations] == [100.0, 200.0]
    assert [o.exchange for o in observations] == ["BINANCE", "BINANCE"]


def test_liquidation_observations_from_records_sorts_by_timestamp() -> None:
    records = [
        Liquidation(exchange="binance", symbol="btcusdt", timestamp=_ts(1), long_liquidation_usd=200.0, short_liquidation_usd=60.0),
        Liquidation(exchange="binance", symbol="btcusdt", timestamp=_ts(0), long_liquidation_usd=100.0, short_liquidation_usd=50.0),
    ]
    observations = liquidation_observations_from_records(records)
    assert [o.long_liquidation_usd for o in observations] == [100.0, 200.0]


def test_liquidation_observations_from_records_handles_empty_list() -> None:
    assert liquidation_observations_from_records([]) == []


def test_ratio_observations_from_records_maps_fields() -> None:
    records = [
        LongShortRatio(exchange="binance", symbol="btcusdt", timestamp=_ts(0), long_account_ratio=0.6, short_account_ratio=0.4),
    ]
    observations = ratio_observations_from_records(records)
    assert observations[0].long_account_ratio == 0.6
    assert observations[0].exchange == "BINANCE"


def test_ratio_observations_from_records_handles_empty_list() -> None:
    assert ratio_observations_from_records([]) == []


def test_open_interest_observations_from_records_maps_fields() -> None:
    records = [
        OpenInterest(exchange="binance", symbol="btcusdt", timestamp=_ts(0), open_interest=1_000_000.0),
    ]
    observations = open_interest_observations_from_records(records)
    assert observations[0].open_interest == 1_000_000.0
    assert observations[0].exchange == "BINANCE"


def test_open_interest_observations_from_records_handles_empty_list() -> None:
    assert open_interest_observations_from_records([]) == []


def test_price_observations_from_candles_maps_fields() -> None:
    candles = [
        Candle(
            exchange="binance", symbol="btcusdt", timeframe=Timeframe.HOUR_1, timestamp=_ts(0),
            open=100.0, high=101.0, low=99.0, close=100.5, volume=10.0,
        ),
    ]
    observations = price_observations_from_candles(candles)
    assert observations[0].close == 100.5
    assert observations[0].exchange == "BINANCE"


def test_price_observations_from_candles_handles_empty_list() -> None:
    assert price_observations_from_candles([]) == []
