from datetime import timedelta

import pytest

from btengine.analysis.premium_discount.config import PremiumDiscountAnalysisConfig, SwingDetectionMethod


def test_defaults_are_valid() -> None:
    config = PremiumDiscountAnalysisConfig()
    assert config.swing_detection_method == SwingDetectionMethod.FRACTAL
    assert config.swing_lookback == 50
    assert config.swing_strength == 2
    assert config.midpoint_ratio == 0.5
    assert config.equilibrium_band_pct is None
    assert config.outlier_zscore_threshold is None
    assert config.expected_interval is None


def test_swing_lookback_must_be_at_least_one() -> None:
    with pytest.raises(ValueError, match="swing_lookback"):
        PremiumDiscountAnalysisConfig(swing_lookback=0, swing_strength=1)


def test_swing_strength_must_be_at_least_one() -> None:
    with pytest.raises(ValueError, match="swing_strength"):
        PremiumDiscountAnalysisConfig(swing_strength=0)


def test_fractal_requires_lookback_covering_strength_on_both_sides() -> None:
    with pytest.raises(ValueError, match="swing_lookback must be >= 2"):
        PremiumDiscountAnalysisConfig(
            swing_detection_method=SwingDetectionMethod.FRACTAL, swing_lookback=4, swing_strength=2
        )


def test_extremum_does_not_require_lookback_covering_strength() -> None:
    config = PremiumDiscountAnalysisConfig(
        swing_detection_method=SwingDetectionMethod.EXTREMUM, swing_lookback=1, swing_strength=5
    )
    assert config.swing_lookback == 1


@pytest.mark.parametrize("ratio", [-0.1, 1.1])
def test_midpoint_ratio_must_be_between_zero_and_one(ratio: float) -> None:
    with pytest.raises(ValueError, match="midpoint_ratio"):
        PremiumDiscountAnalysisConfig(midpoint_ratio=ratio)


@pytest.mark.parametrize("ratio", [0.0, 1.0, 0.5])
def test_midpoint_ratio_boundaries_are_valid(ratio: float) -> None:
    config = PremiumDiscountAnalysisConfig(midpoint_ratio=ratio)
    assert config.midpoint_ratio == ratio


@pytest.mark.parametrize("value", [0.0, -0.1, 1.1])
def test_equilibrium_band_pct_must_be_within_zero_exclusive_to_one(value: float) -> None:
    with pytest.raises(ValueError, match="equilibrium_band_pct"):
        PremiumDiscountAnalysisConfig(equilibrium_band_pct=value)


def test_equilibrium_band_pct_accepts_valid_fraction() -> None:
    config = PremiumDiscountAnalysisConfig(equilibrium_band_pct=0.1)
    assert config.equilibrium_band_pct == 0.1


def test_outlier_zscore_threshold_must_be_positive() -> None:
    with pytest.raises(ValueError, match="outlier_zscore_threshold"):
        PremiumDiscountAnalysisConfig(outlier_zscore_threshold=0)


def test_expected_interval_must_be_positive() -> None:
    with pytest.raises(ValueError, match="expected_interval"):
        PremiumDiscountAnalysisConfig(expected_interval=timedelta(0))


def test_valid_custom_config() -> None:
    config = PremiumDiscountAnalysisConfig(
        swing_detection_method=SwingDetectionMethod.EXTREMUM,
        swing_lookback=20, swing_strength=3, midpoint_ratio=0.6,
        equilibrium_band_pct=0.05, outlier_zscore_threshold=3.0,
        expected_interval=timedelta(hours=1),
    )
    assert config.swing_lookback == 20
    assert config.midpoint_ratio == 0.6
    assert config.equilibrium_band_pct == 0.05
