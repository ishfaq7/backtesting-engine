import math
from datetime import datetime, timedelta, timezone

import pytest

from btengine.analysis.premium_discount.config import PremiumDiscountAnalysisConfig, SwingDetectionMethod
from btengine.analysis.premium_discount.engine import PremiumDiscountAnalysisEngine
from btengine.analysis.premium_discount.errors import PremiumDiscountAnalysisError
from btengine.analysis.premium_discount.models import CandleObservation, PremiumDiscountZone

UTC = timezone.utc


def _candle(hour: int, high: float | None, low: float | None, close: float | None) -> CandleObservation:
    return CandleObservation(
        timestamp=datetime(2024, 1, 1, tzinfo=UTC) + timedelta(hours=hour), high=high, low=low, close=close
    )


_EXTREMUM = PremiumDiscountAnalysisConfig(
    swing_detection_method=SwingDetectionMethod.EXTREMUM, swing_lookback=5, swing_strength=1
)


def _range_candles(last_close: float) -> list[CandleObservation]:
    return [
        _candle(0, high=105, low=95, close=100),
        _candle(1, high=110, low=90, close=100),  # sets active_high=110, active_low=90
        _candle(2, high=108, low=92, close=100),
        _candle(3, high=107, low=93, close=100),
        _candle(4, high=106, low=94, close=last_close),
    ]


def test_analyze_raises_on_empty_input() -> None:
    with pytest.raises(PremiumDiscountAnalysisError):
        PremiumDiscountAnalysisEngine(_EXTREMUM).analyze("BTCUSDT", [])


def test_analyze_raises_when_every_candle_is_missing_fields() -> None:
    candles = [_candle(0, None, None, None), _candle(1, 110, None, 100)]
    with pytest.raises(PremiumDiscountAnalysisError):
        PremiumDiscountAnalysisEngine(_EXTREMUM).analyze("BTCUSDT", candles)


def test_analyze_raises_when_no_swings_are_confirmed() -> None:
    candles = [_candle(h, high=10 + h, low=1 + h, close=5 + h) for h in range(5)]  # monotonic
    config = PremiumDiscountAnalysisConfig(swing_lookback=5, swing_strength=2)
    with pytest.raises(PremiumDiscountAnalysisError):
        PremiumDiscountAnalysisEngine(config).analyze("BTCUSDT", candles)


def test_analyze_raises_on_degenerate_zero_width_range() -> None:
    candles = [_candle(0, high=100.0, low=100.0, close=100.0)]
    with pytest.raises(PremiumDiscountAnalysisError, match="invalid active trading range"):
        PremiumDiscountAnalysisEngine(_EXTREMUM).analyze("BTCUSDT", candles)


def test_analyze_uppercases_symbol() -> None:
    result = PremiumDiscountAnalysisEngine(_EXTREMUM).analyze("btcusdt", _range_candles(100))
    assert result.symbol == "BTCUSDT"


def test_default_timeframe_label_is_unspecified() -> None:
    engine = PremiumDiscountAnalysisEngine(_EXTREMUM)
    assert engine.timeframe_label == "unspecified"
    result = engine.analyze("BTCUSDT", _range_candles(100))
    assert result.timeframe == "unspecified"


def test_custom_timeframe_label_is_used() -> None:
    engine = PremiumDiscountAnalysisEngine(_EXTREMUM, timeframe_label="4h")
    assert engine.timeframe_label == "4h"
    result = engine.analyze("BTCUSDT", _range_candles(100))
    assert result.timeframe == "4h"


def test_analyze_computes_active_range_and_midpoint() -> None:
    result = PremiumDiscountAnalysisEngine(_EXTREMUM).analyze("BTCUSDT", _range_candles(100))
    assert result.active_high == 110.0
    assert result.active_low == 90.0
    assert result.range_size == 20.0
    assert result.midpoint == 100.0
    assert result.sample_size == 5


def test_analyze_current_price_position_pct() -> None:
    result = PremiumDiscountAnalysisEngine(_EXTREMUM).analyze("BTCUSDT", _range_candles(105))
    assert result.current_price == 105.0
    assert math.isclose(result.current_price_position_pct, 75.0)


def test_analyze_premium_zone() -> None:
    result = PremiumDiscountAnalysisEngine(_EXTREMUM).analyze("BTCUSDT", _range_candles(105))
    assert result.zone == PremiumDiscountZone.PREMIUM
    assert math.isclose(result.premium_percentage, 50.0)
    assert result.discount_percentage == 0.0


def test_analyze_discount_zone() -> None:
    result = PremiumDiscountAnalysisEngine(_EXTREMUM).analyze("BTCUSDT", _range_candles(95))
    assert result.zone == PremiumDiscountZone.DISCOUNT
    assert math.isclose(result.discount_percentage, 50.0)
    assert result.premium_percentage == 0.0


def test_analyze_equilibrium_zone_at_exact_midpoint_without_band() -> None:
    result = PremiumDiscountAnalysisEngine(_EXTREMUM).analyze("BTCUSDT", _range_candles(100))
    assert result.zone == PremiumDiscountZone.EQUILIBRIUM


def test_analyze_above_range_zone() -> None:
    result = PremiumDiscountAnalysisEngine(_EXTREMUM).analyze("BTCUSDT", _range_candles(115))
    assert result.zone == PremiumDiscountZone.ABOVE_RANGE
    assert math.isclose(result.premium_percentage, 150.0)
    assert result.discount_percentage == 0.0


def test_analyze_below_range_zone() -> None:
    result = PremiumDiscountAnalysisEngine(_EXTREMUM).analyze("BTCUSDT", _range_candles(80))
    assert result.zone == PremiumDiscountZone.BELOW_RANGE
    assert math.isclose(result.discount_percentage, 200.0)
    assert result.premium_percentage == 0.0


def test_analyze_equilibrium_band_classifies_a_nearby_price_as_equilibrium() -> None:
    config = PremiumDiscountAnalysisConfig(
        swing_detection_method=SwingDetectionMethod.EXTREMUM, swing_lookback=5, swing_strength=1,
        equilibrium_band_pct=0.1,  # +/- 1.0 around midpoint 100, since range=20
    )
    result = PremiumDiscountAnalysisEngine(config).analyze("BTCUSDT", _range_candles(100.5))
    assert result.zone == PremiumDiscountZone.EQUILIBRIUM


def test_analyze_equilibrium_band_does_not_classify_a_far_price_as_equilibrium() -> None:
    config = PremiumDiscountAnalysisConfig(
        swing_detection_method=SwingDetectionMethod.EXTREMUM, swing_lookback=5, swing_strength=1,
        equilibrium_band_pct=0.1,
    )
    result = PremiumDiscountAnalysisEngine(config).analyze("BTCUSDT", _range_candles(101.5))
    assert result.zone == PremiumDiscountZone.PREMIUM


def test_analyze_premium_percentage_is_none_when_midpoint_equals_active_high() -> None:
    config = PremiumDiscountAnalysisConfig(
        swing_detection_method=SwingDetectionMethod.EXTREMUM, swing_lookback=5, swing_strength=1,
        midpoint_ratio=1.0,
    )
    result = PremiumDiscountAnalysisEngine(config).analyze("BTCUSDT", _range_candles(110))
    assert result.midpoint == result.active_high
    assert result.premium_percentage is None


def test_analyze_discount_percentage_is_none_when_midpoint_equals_active_low() -> None:
    config = PremiumDiscountAnalysisConfig(
        swing_detection_method=SwingDetectionMethod.EXTREMUM, swing_lookback=5, swing_strength=1,
        midpoint_ratio=0.0,
    )
    result = PremiumDiscountAnalysisEngine(config).analyze("BTCUSDT", _range_candles(85))
    assert result.midpoint == result.active_low
    assert result.discount_percentage is None


def test_analyze_confidence_level_reflects_data_sufficiency() -> None:
    config = PremiumDiscountAnalysisConfig(
        swing_detection_method=SwingDetectionMethod.EXTREMUM, swing_lookback=50, swing_strength=1
    )
    candles = _range_candles(100)  # 5 candles
    result = PremiumDiscountAnalysisEngine(config).analyze("BTCUSDT", candles)
    assert result.confidence_level == pytest.approx(5 / 50)


def test_analyze_confidence_level_is_capped_at_one() -> None:
    config = PremiumDiscountAnalysisConfig(
        swing_detection_method=SwingDetectionMethod.EXTREMUM, swing_lookback=3, swing_strength=1
    )
    result = PremiumDiscountAnalysisEngine(config).analyze("BTCUSDT", _range_candles(100))
    assert result.confidence_level == 1.0


def test_analyze_excludes_candles_with_missing_fields() -> None:
    candles = _range_candles(100) + [_candle(5, high=None, low=None, close=None)]
    result = PremiumDiscountAnalysisEngine(_EXTREMUM).analyze("BTCUSDT", candles)
    assert result.sample_size == 5


def test_analyze_excludes_invalid_candles_where_high_is_below_low() -> None:
    candles = _range_candles(100) + [_candle(5, high=50, low=200, close=100)]
    result = PremiumDiscountAnalysisEngine(_EXTREMUM).analyze("BTCUSDT", candles)
    assert result.sample_size == 5
    assert result.active_high == 110.0


def test_analyze_duplicate_timestamp_keeps_last_given_candle() -> None:
    timestamp = datetime(2024, 1, 1, tzinfo=UTC)
    candles = [
        CandleObservation(timestamp=timestamp, high=110.0, low=90.0, close=95.0),
        CandleObservation(timestamp=timestamp, high=110.0, low=90.0, close=105.0),
    ]
    result = PremiumDiscountAnalysisEngine(_EXTREMUM).analyze("BTCUSDT", candles)
    assert result.current_price == 105.0
    assert result.sample_size == 1


def test_analyze_sorts_out_of_order_candles() -> None:
    candles = list(reversed(_range_candles(100)))
    result = PremiumDiscountAnalysisEngine(_EXTREMUM).analyze("BTCUSDT", candles)
    assert result.as_of == datetime(2024, 1, 1, 4, tzinfo=UTC)
    assert result.current_price == 100.0


def test_validate_delegates_to_premium_discount_validator() -> None:
    naive = CandleObservation(timestamp=datetime(2024, 1, 1), high=110.0, low=90.0, close=100.0)
    issues = PremiumDiscountAnalysisEngine(_EXTREMUM).validate([naive])
    assert any(i.severity == "ERROR" and "timezone-aware" in i.message for i in issues)


# --- historical replay consistency ---------------------------------------


def test_historical_replay_never_repaints_a_confirmed_swing() -> None:
    highs = [10, 12, 15, 12, 10, 9, 8, 7, 6]
    lows = [5, 4, 3, 4, 5, 6, 7, 8, 9]
    full_series = [
        _candle(h, high=highs[h], low=lows[h], close=(highs[h] + lows[h]) / 2) for h in range(len(highs))
    ]
    config = PremiumDiscountAnalysisConfig(swing_lookback=9, swing_strength=2)
    engine = PremiumDiscountAnalysisEngine(config)

    # The peak at index 2 (high=15, low=3) is confirmed once 2 bars of future
    # context exist, i.e. from a 5-candle prefix onward. It must report the
    # same active_high/active_low at every longer prefix - no repainting.
    results = [engine.analyze("BTCUSDT", full_series[: n + 1]) for n in range(4, len(full_series))]
    for result in results:
        assert result.active_high == 15
        assert result.active_low == 3
