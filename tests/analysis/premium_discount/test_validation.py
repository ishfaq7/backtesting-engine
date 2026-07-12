from datetime import datetime, timedelta, timezone

from btengine.analysis.premium_discount.config import PremiumDiscountAnalysisConfig
from btengine.analysis.premium_discount.models import CandleObservation
from btengine.analysis.premium_discount.validation import PremiumDiscountValidator

UTC = timezone.utc


def _candle(hour: int, high: float | None = 110.0, low: float | None = 90.0, close: float | None = 100.0) -> CandleObservation:
    return CandleObservation(
        timestamp=datetime(2024, 1, 1, tzinfo=UTC) + timedelta(hours=hour), high=high, low=low, close=close
    )


def test_well_formed_series_has_no_issues() -> None:
    candles = [_candle(h) for h in range(5)]
    assert PremiumDiscountValidator().validate(candles) == []


def test_missing_high_is_flagged_as_warning() -> None:
    candles = [_candle(0), _candle(1, high=None)]
    issues = PremiumDiscountValidator().validate(candles)
    assert any(i.severity == "WARNING" and "missing" in i.message for i in issues)


def test_missing_low_is_flagged_as_warning() -> None:
    candles = [_candle(0), _candle(1, low=None)]
    issues = PremiumDiscountValidator().validate(candles)
    assert any(i.severity == "WARNING" and "missing" in i.message for i in issues)


def test_missing_close_is_flagged_as_warning() -> None:
    candles = [_candle(0), _candle(1, close=None)]
    issues = PremiumDiscountValidator().validate(candles)
    assert any(i.severity == "WARNING" and "missing" in i.message for i in issues)


def test_invalid_candle_high_below_low_is_flagged_as_error() -> None:
    candles = [_candle(0, high=90.0, low=110.0)]
    issues = PremiumDiscountValidator().validate(candles)
    assert any(i.severity == "ERROR" and "invalid candle" in i.message for i in issues)


def test_naive_timestamp_is_flagged_as_error() -> None:
    candle = CandleObservation(timestamp=datetime(2024, 1, 1), high=110.0, low=90.0, close=100.0)
    issues = PremiumDiscountValidator().validate([candle])
    assert any(i.severity == "ERROR" and "timezone-aware" in i.message for i in issues)


def test_duplicate_timestamp_is_flagged_as_error() -> None:
    candles = [_candle(0, close=100.0), _candle(0, close=101.0)]
    issues = PremiumDiscountValidator().validate(candles)
    assert any(i.severity == "ERROR" and "duplicate" in i.message for i in issues)


def test_outliers_are_not_checked_when_threshold_unset() -> None:
    candles = [_candle(h, close=100.0) for h in range(10)] + [_candle(10, close=1_000_000.0)]
    issues = PremiumDiscountValidator().validate(candles)
    assert not any("outlier" in i.message for i in issues)


def test_outliers_are_flagged_when_threshold_configured() -> None:
    candles = [_candle(h, close=100.0) for h in range(10)] + [_candle(10, close=1_000_000.0)]
    config = PremiumDiscountAnalysisConfig(outlier_zscore_threshold=2.0)
    issues = PremiumDiscountValidator(config).validate(candles)
    assert any(i.severity == "WARNING" and "outlier" in i.message for i in issues)


def test_outlier_check_skips_when_fewer_than_two_values() -> None:
    config = PremiumDiscountAnalysisConfig(outlier_zscore_threshold=2.0)
    issues = PremiumDiscountValidator(config).validate([_candle(0)])
    assert not any("outlier" in i.message for i in issues)


def test_outlier_check_skips_when_stdev_is_zero() -> None:
    candles = [_candle(h, close=100.0) for h in range(5)]
    config = PremiumDiscountAnalysisConfig(outlier_zscore_threshold=1.0)
    issues = PremiumDiscountValidator(config).validate(candles)
    assert not any("outlier" in i.message for i in issues)


def test_outlier_check_skips_missing_close_without_flagging_it() -> None:
    closes = [100.0, 101.0, 102.0, 103.0]
    candles = [_candle(h, close=c) for h, c in enumerate(closes)] + [_candle(len(closes), close=None)]
    config = PremiumDiscountAnalysisConfig(outlier_zscore_threshold=3.0)
    issues = PremiumDiscountValidator(config).validate(candles)
    outlier_issues = [i for i in issues if "outlier" in i.message]
    assert not any(i.timestamp == candles[-1].timestamp for i in outlier_issues)


def test_gaps_are_not_checked_when_expected_interval_unset() -> None:
    candles = [_candle(0), _candle(100)]
    issues = PremiumDiscountValidator().validate(candles)
    assert not any("gap" in i.message for i in issues)


def test_gap_is_flagged_when_expected_interval_configured() -> None:
    candles = [_candle(0), _candle(100)]
    config = PremiumDiscountAnalysisConfig(expected_interval=timedelta(hours=1))
    issues = PremiumDiscountValidator(config).validate(candles)
    assert any(i.severity == "WARNING" and "gap" in i.message for i in issues)


def test_no_gap_flagged_when_interval_is_within_expected() -> None:
    candles = [_candle(0), _candle(1)]
    config = PremiumDiscountAnalysisConfig(expected_interval=timedelta(hours=1))
    issues = PremiumDiscountValidator(config).validate(candles)
    assert not any("gap" in i.message for i in issues)


def test_gap_check_sorts_out_of_order_candles() -> None:
    candles = [_candle(100), _candle(0)]
    config = PremiumDiscountAnalysisConfig(expected_interval=timedelta(hours=1))
    issues = PremiumDiscountValidator(config).validate(candles)
    assert any("gap" in i.message for i in issues)
