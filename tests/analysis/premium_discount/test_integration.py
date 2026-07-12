from datetime import datetime, timedelta, timezone

from btengine.analysis.premium_discount.integration import observations_from_candles
from btengine.data.schema import Candle, Timeframe

UTC = timezone.utc


def _candle(hour: int, high: float, low: float, close: float) -> Candle:
    return Candle(
        exchange="binance", symbol="btcusdt", timeframe=Timeframe.HOUR_1,
        timestamp=datetime(2024, 1, 1, tzinfo=UTC) + timedelta(hours=hour),
        open=close, high=high, low=low, close=close, volume=100.0,
    )


def test_observations_from_candles_maps_fields() -> None:
    candles = [_candle(0, high=110.0, low=90.0, close=100.0), _candle(1, high=112.0, low=92.0, close=102.0)]
    observations = observations_from_candles(candles)
    assert [o.high for o in observations] == [110.0, 112.0]
    assert [o.low for o in observations] == [90.0, 92.0]
    assert [o.close for o in observations] == [100.0, 102.0]
    assert [o.timestamp for o in observations] == [c.timestamp for c in candles]


def test_observations_from_candles_sorts_by_timestamp() -> None:
    candles = [
        _candle(1, high=112.0, low=92.0, close=102.0),
        _candle(0, high=110.0, low=90.0, close=100.0),
    ]
    observations = observations_from_candles(candles)
    assert [o.close for o in observations] == [100.0, 102.0]


def test_observations_from_candles_handles_empty_list() -> None:
    assert observations_from_candles([]) == []
