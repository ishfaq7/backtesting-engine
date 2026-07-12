import math
import statistics
from datetime import datetime, timedelta, timezone

import pytest

from btengine.analysis.open_interest.config import OpenInterestAnalysisConfig
from btengine.analysis.open_interest.engine import OpenInterestAnalysisEngine
from btengine.analysis.open_interest.errors import OpenInterestAnalysisError
from btengine.analysis.open_interest.models import OiDirection, OpenInterestObservation

UTC = timezone.utc


def _obs(hour: int, oi: float | None) -> OpenInterestObservation:
    return OpenInterestObservation(
        timestamp=datetime(2024, 1, 1, tzinfo=UTC) + timedelta(hours=hour), open_interest=oi
    )


def test_analyze_raises_on_empty_input() -> None:
    with pytest.raises(OpenInterestAnalysisError):
        OpenInterestAnalysisEngine().analyze("BTCUSDT", [])


def test_analyze_raises_when_every_value_is_missing() -> None:
    observations = [_obs(0, None), _obs(1, None)]
    with pytest.raises(OpenInterestAnalysisError):
        OpenInterestAnalysisEngine().analyze("BTCUSDT", observations)


def test_analyze_uppercases_symbol() -> None:
    result = OpenInterestAnalysisEngine().analyze("btcusdt", [_obs(0, 1_000_000.0)])
    assert result.symbol == "BTCUSDT"


def test_default_source_label_is_aggregated() -> None:
    engine = OpenInterestAnalysisEngine()
    assert engine.source_label == "aggregated"
    result = engine.analyze("BTCUSDT", [_obs(0, 1_000_000.0)])
    assert result.source == "aggregated"


def test_custom_source_label_is_used_for_exchange_specific_oi() -> None:
    engine = OpenInterestAnalysisEngine(source_label="binance")
    assert engine.source_label == "binance"
    result = engine.analyze("BTCUSDT", [_obs(0, 1_000_000.0)])
    assert result.source == "binance"


def test_analyze_single_observation_has_no_previous_or_change() -> None:
    result = OpenInterestAnalysisEngine().analyze("BTCUSDT", [_obs(0, 1_000_000.0)])
    assert result.current_oi == 1_000_000.0
    assert result.previous_oi is None
    assert result.oi_change is None
    assert result.oi_change_pct is None
    assert result.oi_trend == OiDirection.UNKNOWN
    assert result.oi_trend_value is None
    assert result.oi_momentum == OiDirection.UNKNOWN
    assert result.oi_momentum_value is None
    assert result.oi_volatility is None
    assert result.is_abnormal_spike is None
    assert result.spike_magnitude is None
    assert result.sample_size == 1


def test_analyze_computes_current_previous_and_change() -> None:
    observations = [_obs(0, 1_000_000.0), _obs(1, 1_100_000.0)]
    result = OpenInterestAnalysisEngine().analyze("BTCUSDT", observations)
    assert result.current_oi == 1_100_000.0
    assert result.previous_oi == 1_000_000.0
    assert math.isclose(result.oi_change, 100_000.0)
    assert math.isclose(result.oi_change_pct, 0.1)


def test_analyze_oi_change_pct_is_none_when_previous_is_zero() -> None:
    observations = [_obs(0, 0.0), _obs(1, 1_000.0)]
    result = OpenInterestAnalysisEngine().analyze("BTCUSDT", observations)
    assert result.oi_change_pct is None


def test_analyze_rising_series() -> None:
    values = [1_000_000.0, 1_010_000.0, 1_020_000.0, 1_030_000.0, 1_040_000.0, 1_050_000.0]
    observations = [_obs(h, v) for h, v in enumerate(values)]
    config = OpenInterestAnalysisConfig(
        trend_window=4, momentum_window=4, volatility_window=4, spike_window=4
    )
    result = OpenInterestAnalysisEngine(config).analyze("BTCUSDT", observations)

    assert result.oi_trend == OiDirection.RISING
    assert math.isclose(result.oi_trend_value, 10_000.0, rel_tol=1e-9)

    assert result.oi_momentum == OiDirection.RISING
    assert math.isclose(result.oi_momentum_value, 20_000.0, rel_tol=1e-9)

    expected_volatility = statistics.stdev(values[-4:])
    assert math.isclose(result.oi_volatility, expected_volatility)

    assert math.isclose(result.historical_average, statistics.mean(values))
    assert result.historical_maximum == max(values)
    assert result.historical_minimum == min(values)
    assert result.sample_size == 6
    assert result.confidence_level == 1.0


def test_analyze_falling_series() -> None:
    values = [1_050_000.0, 1_040_000.0, 1_030_000.0, 1_020_000.0]
    observations = [_obs(h, v) for h, v in enumerate(values)]
    config = OpenInterestAnalysisConfig(trend_window=4, momentum_window=4, volatility_window=4)
    result = OpenInterestAnalysisEngine(config).analyze("BTCUSDT", observations)

    assert result.oi_trend == OiDirection.FALLING
    assert result.oi_trend_value < 0
    assert result.oi_momentum == OiDirection.FALLING
    assert result.oi_momentum_value < 0


def test_analyze_flat_series() -> None:
    values = [1_000_000.0, 1_000_000.0, 1_000_000.0, 1_000_000.0]
    observations = [_obs(h, v) for h, v in enumerate(values)]
    config = OpenInterestAnalysisConfig(trend_window=4, momentum_window=4, volatility_window=4)
    result = OpenInterestAnalysisEngine(config).analyze("BTCUSDT", observations)

    assert result.oi_trend == OiDirection.FLAT
    assert math.isclose(result.oi_trend_value, 0.0, abs_tol=1e-3)
    assert result.oi_momentum == OiDirection.FLAT
    assert result.oi_momentum_value == 0.0
    assert result.oi_volatility == 0.0


def test_analyze_confidence_level_reflects_data_sufficiency() -> None:
    observations = [_obs(h, 1_000_000.0) for h in range(3)]
    result = OpenInterestAnalysisEngine().analyze("BTCUSDT", observations)
    assert result.confidence_level == pytest.approx(3 / 30)


def test_analyze_confidence_level_is_capped_at_one() -> None:
    observations = [_obs(h, 1_000_000.0) for h in range(100)]
    result = OpenInterestAnalysisEngine().analyze("BTCUSDT", observations)
    assert result.confidence_level == 1.0


def test_analyze_historical_window_limits_historical_stats() -> None:
    values = [1_000_000.0, 1_010_000.0, 1_020_000.0, 5_000_000.0]
    observations = [_obs(h, v) for h, v in enumerate(values)]
    config = OpenInterestAnalysisConfig(historical_window=2)
    result = OpenInterestAnalysisEngine(config).analyze("BTCUSDT", observations)
    assert result.historical_maximum == 5_000_000.0
    assert result.historical_minimum == 1_020_000.0
    assert math.isclose(result.historical_average, (1_020_000.0 + 5_000_000.0) / 2)


def test_analyze_excludes_missing_values() -> None:
    observations = [_obs(0, 1_000_000.0), _obs(1, None), _obs(2, 1_020_000.0)]
    result = OpenInterestAnalysisEngine().analyze("BTCUSDT", observations)
    assert result.current_oi == 1_020_000.0
    assert result.previous_oi == 1_000_000.0
    assert result.sample_size == 2


def test_analyze_duplicate_timestamp_keeps_last_given_value() -> None:
    timestamp = datetime(2024, 1, 1, tzinfo=UTC)
    observations = [
        OpenInterestObservation(timestamp=timestamp, open_interest=1_000_000.0),
        OpenInterestObservation(timestamp=timestamp, open_interest=1_100_000.0),
    ]
    result = OpenInterestAnalysisEngine().analyze("BTCUSDT", observations)
    assert result.current_oi == 1_100_000.0
    assert result.sample_size == 1


def test_analyze_sorts_out_of_order_observations() -> None:
    observations = [_obs(1, 1_100_000.0), _obs(0, 1_000_000.0)]
    result = OpenInterestAnalysisEngine().analyze("BTCUSDT", observations)
    assert result.current_oi == 1_100_000.0
    assert result.previous_oi == 1_000_000.0
    assert result.as_of == datetime(2024, 1, 1, 1, tzinfo=UTC)


def test_validate_delegates_to_open_interest_data_validator() -> None:
    naive = OpenInterestObservation(timestamp=datetime(2024, 1, 1), open_interest=1_000_000.0)
    issues = OpenInterestAnalysisEngine().validate([naive])
    assert any(i.severity == "ERROR" and "timezone-aware" in i.message for i in issues)


# --- spike detection -----------------------------------------------------


def test_spike_is_unclassified_with_too_little_history() -> None:
    values = [1_000_000.0, 1_010_000.0, 1_020_000.0]
    observations = [_obs(h, v) for h, v in enumerate(values)]
    config = OpenInterestAnalysisConfig(spike_window=5)
    result = OpenInterestAnalysisEngine(config).analyze("BTCUSDT", observations)
    assert result.is_abnormal_spike is None
    assert result.spike_magnitude is None


def test_spike_magnitude_is_unclassified_when_baseline_stdev_is_zero() -> None:
    values = [100.0, 101.0, 102.0, 103.0, 999.0]
    observations = [_obs(h, v) for h, v in enumerate(values)]
    config = OpenInterestAnalysisConfig(spike_window=5)
    result = OpenInterestAnalysisEngine(config).analyze("BTCUSDT", observations)
    assert result.is_abnormal_spike is None
    assert result.spike_magnitude is None


def test_spike_magnitude_is_computed_but_unclassified_without_threshold() -> None:
    values = [100.0, 102.0, 101.0, 104.0, 200.0]
    observations = [_obs(h, v) for h, v in enumerate(values)]
    config = OpenInterestAnalysisConfig(spike_window=5)
    result = OpenInterestAnalysisEngine(config).analyze("BTCUSDT", observations)

    changes = [values[i] - values[i - 1] for i in range(1, len(values))]
    baseline, latest = changes[:-1], changes[-1]
    expected_zscore = (latest - statistics.mean(baseline)) / statistics.stdev(baseline)

    assert result.spike_magnitude == pytest.approx(expected_zscore)
    assert result.is_abnormal_spike is None


def test_spike_is_flagged_true_when_threshold_is_exceeded() -> None:
    values = [100.0, 102.0, 101.0, 104.0, 200.0]
    observations = [_obs(h, v) for h, v in enumerate(values)]
    config = OpenInterestAnalysisConfig(spike_window=5, spike_zscore_threshold=3.0)
    result = OpenInterestAnalysisEngine(config).analyze("BTCUSDT", observations)
    assert result.is_abnormal_spike is True


def test_spike_is_flagged_false_when_threshold_is_not_exceeded() -> None:
    values = [100.0, 102.0, 101.0, 104.0, 200.0]
    observations = [_obs(h, v) for h, v in enumerate(values)]
    config = OpenInterestAnalysisConfig(spike_window=5, spike_zscore_threshold=1000.0)
    result = OpenInterestAnalysisEngine(config).analyze("BTCUSDT", observations)
    assert result.is_abnormal_spike is False
