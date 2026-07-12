from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from btengine.analysis.premium_discount.config import PremiumDiscountAnalysisConfig, SwingDetectionMethod
from btengine.analysis.premium_discount.models import CandleObservation, SwingKind
from btengine.analysis.premium_discount.swings import detect_swings

UTC = timezone.utc


def _candle(hour: int, high: float, low: float, close: float | None = None) -> CandleObservation:
    return CandleObservation(
        timestamp=datetime(2024, 1, 1, tzinfo=UTC) + timedelta(hours=hour),
        high=high, low=low, close=close if close is not None else (high + low) / 2,
    )


def test_fractal_confirms_a_symmetric_local_extremum() -> None:
    candles = [
        _candle(0, high=10, low=5),
        _candle(1, high=12, low=4),
        _candle(2, high=15, low=2),
        _candle(3, high=12, low=4),
        _candle(4, high=10, low=5),
    ]
    config = PremiumDiscountAnalysisConfig(
        swing_detection_method=SwingDetectionMethod.FRACTAL, swing_lookback=5, swing_strength=2
    )
    swings = detect_swings(candles, config)

    highs = [s for s in swings if s.kind is SwingKind.HIGH]
    lows = [s for s in swings if s.kind is SwingKind.LOW]
    assert len(highs) == 1
    assert highs[0].price == 15
    assert highs[0].timestamp == candles[2].timestamp
    assert len(lows) == 1
    assert lows[0].price == 2
    assert lows[0].timestamp == candles[2].timestamp


def test_fractal_does_not_confirm_a_monotonic_series() -> None:
    candles = [_candle(h, high=10 + h, low=1 + h) for h in range(5)]
    config = PremiumDiscountAnalysisConfig(swing_lookback=5, swing_strength=2)
    assert detect_swings(candles, config) == []


def test_fractal_does_not_confirm_a_tie() -> None:
    candles = [
        _candle(0, high=10, low=5),
        _candle(1, high=12, low=4),
        _candle(2, high=12, low=4),  # ties the neighbor - strict inequality required
        _candle(3, high=12, low=4),
        _candle(4, high=10, low=5),
    ]
    config = PremiumDiscountAnalysisConfig(swing_lookback=5, swing_strength=2)
    assert detect_swings(candles, config) == []


def test_fractal_uses_only_the_last_swing_lookback_candles() -> None:
    early_spike = [_candle(0, high=100, low=1), _candle(1, high=5, low=1), _candle(2, high=5, low=1)]
    later_candles = [
        _candle(3, high=10, low=5), _candle(4, high=12, low=4), _candle(5, high=15, low=2),
        _candle(6, high=12, low=4), _candle(7, high=10, low=5),
    ]
    candles = early_spike + later_candles
    config = PremiumDiscountAnalysisConfig(swing_lookback=5, swing_strength=2)
    swings = detect_swings(candles, config)
    highs = [s.price for s in swings if s.kind is SwingKind.HIGH]
    assert highs == [15]  # the early_spike's 100 high is outside the lookback window


def test_fractal_requires_swing_strength_bars_on_both_sides() -> None:
    candles = [_candle(h, high=10 + h, low=1) for h in range(3)]  # monotonic increasing
    config = PremiumDiscountAnalysisConfig(swing_lookback=3, swing_strength=1)
    assert detect_swings(candles, config) == []


def test_extremum_returns_the_single_highest_high_and_lowest_low() -> None:
    candles = [
        _candle(0, high=10, low=5),
        _candle(1, high=20, low=1),
        _candle(2, high=15, low=8),
    ]
    config = PremiumDiscountAnalysisConfig(
        swing_detection_method=SwingDetectionMethod.EXTREMUM, swing_lookback=3, swing_strength=1
    )
    swings = detect_swings(candles, config)
    assert len(swings) == 2
    high = next(s for s in swings if s.kind is SwingKind.HIGH)
    low = next(s for s in swings if s.kind is SwingKind.LOW)
    assert high.price == 20
    assert high.timestamp == candles[1].timestamp
    assert low.price == 1
    assert low.timestamp == candles[1].timestamp


def test_extremum_handles_empty_window() -> None:
    config = PremiumDiscountAnalysisConfig(
        swing_detection_method=SwingDetectionMethod.EXTREMUM, swing_lookback=5, swing_strength=1
    )
    assert detect_swings([], config) == []


def test_extremum_uses_only_the_last_swing_lookback_candles() -> None:
    candles = [_candle(0, high=1000, low=0.1)] + [_candle(h, high=10, low=5) for h in range(1, 4)]
    config = PremiumDiscountAnalysisConfig(
        swing_detection_method=SwingDetectionMethod.EXTREMUM, swing_lookback=3, swing_strength=1
    )
    swings = detect_swings(candles, config)
    high = next(s for s in swings if s.kind is SwingKind.HIGH)
    assert high.price == 10  # the 1000 high is outside the lookback window


def test_unsupported_swing_detection_method_raises_not_implemented_error() -> None:
    fake_config = SimpleNamespace(swing_lookback=5, swing_detection_method="UNSUPPORTED")
    candles = [_candle(h, high=10, low=1) for h in range(5)]
    with pytest.raises(NotImplementedError):
        detect_swings(candles, fake_config)
