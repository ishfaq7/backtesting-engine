from datetime import timedelta

import pytest

from btengine.analysis.funding_rate.config import FundingRateAnalysisConfig


def test_defaults_are_valid() -> None:
    config = FundingRateAnalysisConfig()
    assert config.trend_window == 8
    assert config.momentum_window == 8
    assert config.volatility_window == 30
    assert config.historical_window is None
    assert config.outlier_zscore_threshold is None
    assert config.expected_interval is None


@pytest.mark.parametrize("field", ["trend_window", "momentum_window", "volatility_window"])
def test_window_must_be_at_least_two(field: str) -> None:
    with pytest.raises(ValueError, match=field):
        FundingRateAnalysisConfig(**{field: 1})


def test_historical_window_must_be_at_least_one() -> None:
    with pytest.raises(ValueError, match="historical_window"):
        FundingRateAnalysisConfig(historical_window=0)


def test_outlier_zscore_threshold_must_be_positive() -> None:
    with pytest.raises(ValueError, match="outlier_zscore_threshold"):
        FundingRateAnalysisConfig(outlier_zscore_threshold=0)


def test_expected_interval_must_be_positive() -> None:
    with pytest.raises(ValueError, match="expected_interval"):
        FundingRateAnalysisConfig(expected_interval=timedelta(0))


def test_valid_custom_config() -> None:
    config = FundingRateAnalysisConfig(
        trend_window=4, momentum_window=6, volatility_window=12,
        historical_window=100, outlier_zscore_threshold=3.0,
        expected_interval=timedelta(hours=8),
    )
    assert config.trend_window == 4
    assert config.historical_window == 100
    assert config.outlier_zscore_threshold == 3.0
    assert config.expected_interval == timedelta(hours=8)
