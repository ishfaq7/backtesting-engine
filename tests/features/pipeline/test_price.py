import math
from datetime import datetime, timedelta, timezone

from btengine.data.schema import Candle, Timeframe
from btengine.features.pipeline.price import PriceFeatures

UTC = timezone.utc


def _candle(hour: int, close: float, *, high: float | None = None, low: float | None = None) -> Candle:
    high = close + 1 if high is None else high
    low = close - 1 if low is None else low
    return Candle(
        exchange="binance", symbol="btcusdt", timeframe=Timeframe.HOUR_1,
        timestamp=datetime(2024, 1, 1, tzinfo=UTC) + timedelta(hours=hour),
        open=close, high=high, low=low, close=close, volume=100.0,
    )


def test_module_name_is_price() -> None:
    assert PriceFeatures().module_name == "price"


def test_compute_returns_empty_list_for_no_candles() -> None:
    assert PriceFeatures().compute("BTCUSDT", []) == []


def test_compute_emits_return_pct_and_log_return() -> None:
    candles = [_candle(h, close=100.0 + h) for h in range(5)]
    features = PriceFeatures().compute("BTCUSDT", candles)
    names = {f.feature_name for f in features}
    assert "price.return_pct" in names
    assert "price.log_return" in names
    assert all(f.symbol == "BTCUSDT" for f in features)


def test_compute_emits_true_range() -> None:
    candles = [_candle(h, close=100.0) for h in range(3)]
    features = PriceFeatures().compute("BTCUSDT", candles)
    true_range = [f for f in features if f.feature_name == "price.true_range"]
    assert len(true_range) == 3
    for f in true_range:
        assert f.value >= 0


def test_compute_windows_are_reflected_in_feature_names() -> None:
    candles = [_candle(h, close=100.0 + h) for h in range(10)]
    module = PriceFeatures(sma_window=3, ema_window=4, atr_window=5, volatility_window=6)
    features = module.compute("BTCUSDT", candles)
    names = {f.feature_name for f in features}
    assert "price.sma_3" in names
    assert "price.ema_4" in names
    assert "price.atr_5" in names
    assert "price.volatility_6" in names


def test_compute_atr_requires_enough_history_before_emitting() -> None:
    candles = [_candle(h, close=100.0) for h in range(3)]
    module = PriceFeatures(atr_window=14)
    features = module.compute("BTCUSDT", candles)
    atr_values = [f for f in features if f.feature_name == "price.atr_14"]
    assert atr_values == []


def test_compute_high_low_range_pct() -> None:
    candles = [_candle(0, close=100.0, high=110.0, low=90.0)]
    features = PriceFeatures().compute("BTCUSDT", candles)
    range_pct = next(f for f in features if f.feature_name == "price.high_low_range_pct")
    assert math.isclose(range_pct.value, 0.2)


def test_compute_sorts_out_of_order_candles_by_timestamp() -> None:
    candles = [_candle(1, close=101.0), _candle(0, close=100.0)]
    features = PriceFeatures().compute("BTCUSDT", candles)
    returns = [f for f in features if f.feature_name == "price.return_pct"]
    assert len(returns) == 1
    assert math.isclose(returns[0].value, 0.01)
