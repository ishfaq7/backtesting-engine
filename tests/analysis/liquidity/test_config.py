from datetime import timedelta

import pytest

from btengine.analysis.liquidity.config import AggregationMethod, LiquidityAnalysisConfig


def test_defaults_are_valid() -> None:
    config = LiquidityAnalysisConfig()
    assert config.analysis_window == 30
    assert config.spike_window == 30
    assert config.exchange_selection is None
    assert config.aggregation_method == AggregationMethod.SUM
    assert config.outlier_zscore_threshold is None
    assert config.spike_zscore_threshold is None
    assert config.expected_interval is None


def test_analysis_window_must_be_at_least_two() -> None:
    with pytest.raises(ValueError, match="analysis_window"):
        LiquidityAnalysisConfig(analysis_window=1)


def test_spike_window_must_be_at_least_two() -> None:
    with pytest.raises(ValueError, match="spike_window"):
        LiquidityAnalysisConfig(spike_window=1)


def test_exchange_selection_must_not_be_empty_tuple() -> None:
    with pytest.raises(ValueError, match="exchange_selection"):
        LiquidityAnalysisConfig(exchange_selection=())


def test_exchange_selection_must_not_contain_blank_entries() -> None:
    with pytest.raises(ValueError, match="exchange_selection"):
        LiquidityAnalysisConfig(exchange_selection=("BINANCE", "  "))


def test_exchange_selection_accepts_valid_tuple() -> None:
    config = LiquidityAnalysisConfig(exchange_selection=("BINANCE", "OKX"))
    assert config.exchange_selection == ("BINANCE", "OKX")


def test_outlier_zscore_threshold_must_be_positive() -> None:
    with pytest.raises(ValueError, match="outlier_zscore_threshold"):
        LiquidityAnalysisConfig(outlier_zscore_threshold=0)


def test_spike_zscore_threshold_must_be_positive() -> None:
    with pytest.raises(ValueError, match="spike_zscore_threshold"):
        LiquidityAnalysisConfig(spike_zscore_threshold=0)


def test_expected_interval_must_be_positive() -> None:
    with pytest.raises(ValueError, match="expected_interval"):
        LiquidityAnalysisConfig(expected_interval=timedelta(0))


def test_valid_custom_config() -> None:
    config = LiquidityAnalysisConfig(
        analysis_window=10, spike_window=15, exchange_selection=("BINANCE",),
        aggregation_method=AggregationMethod.MEAN, outlier_zscore_threshold=3.0,
        spike_zscore_threshold=2.5, expected_interval=timedelta(hours=1),
    )
    assert config.analysis_window == 10
    assert config.aggregation_method == AggregationMethod.MEAN
