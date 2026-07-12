import math
import statistics
from datetime import datetime, timedelta, timezone

import pytest

from btengine.analysis.funding_rate.config import FundingRateAnalysisConfig
from btengine.analysis.funding_rate.engine import FundingRateAnalysisEngine
from btengine.analysis.funding_rate.errors import FundingRateAnalysisError
from btengine.analysis.funding_rate.models import FundingDirection, FundingRateObservation

UTC = timezone.utc


def _obs(hour: int, rate: float | None) -> FundingRateObservation:
    return FundingRateObservation(
        timestamp=datetime(2024, 1, 1, tzinfo=UTC) + timedelta(hours=hour), funding_rate=rate
    )


def test_analyze_raises_on_empty_input() -> None:
    with pytest.raises(FundingRateAnalysisError):
        FundingRateAnalysisEngine().analyze("BTCUSDT", [])


def test_analyze_raises_when_every_value_is_missing() -> None:
    observations = [_obs(0, None), _obs(1, None)]
    with pytest.raises(FundingRateAnalysisError):
        FundingRateAnalysisEngine().analyze("BTCUSDT", observations)


def test_analyze_uppercases_symbol() -> None:
    result = FundingRateAnalysisEngine().analyze("btcusdt", [_obs(0, 0.0001)])
    assert result.symbol == "BTCUSDT"


def test_analyze_single_observation_has_no_previous_or_change() -> None:
    result = FundingRateAnalysisEngine().analyze("BTCUSDT", [_obs(0, 0.0001)])
    assert result.current_funding == 0.0001
    assert result.previous_funding is None
    assert result.funding_change is None
    assert result.funding_change_pct is None
    assert result.funding_trend == FundingDirection.UNKNOWN
    assert result.funding_trend_value is None
    assert result.funding_momentum == FundingDirection.UNKNOWN
    assert result.funding_momentum_value is None
    assert result.funding_volatility is None
    assert result.sample_size == 1


def test_analyze_computes_current_previous_and_change() -> None:
    observations = [_obs(0, 0.0005), _obs(1, 0.0006)]
    result = FundingRateAnalysisEngine().analyze("BTCUSDT", observations)
    assert result.current_funding == 0.0006
    assert result.previous_funding == 0.0005
    assert math.isclose(result.funding_change, 0.0001)
    assert math.isclose(result.funding_change_pct, 0.2)


def test_analyze_funding_change_pct_is_none_when_previous_is_zero() -> None:
    observations = [_obs(0, 0.0), _obs(1, 0.0001)]
    result = FundingRateAnalysisEngine().analyze("BTCUSDT", observations)
    assert result.funding_change_pct is None


def test_analyze_rising_series() -> None:
    rates = [0.0001, 0.0002, 0.0003, 0.0004, 0.0005, 0.0006]
    observations = [_obs(h, r) for h, r in enumerate(rates)]
    config = FundingRateAnalysisConfig(trend_window=4, momentum_window=4, volatility_window=4)
    result = FundingRateAnalysisEngine(config).analyze("BTCUSDT", observations)

    assert result.funding_trend == FundingDirection.RISING
    assert math.isclose(result.funding_trend_value, 0.0001, abs_tol=1e-12)

    assert result.funding_momentum == FundingDirection.RISING
    assert math.isclose(result.funding_momentum_value, 0.0002, abs_tol=1e-12)

    expected_volatility = statistics.stdev(rates[-4:])
    assert math.isclose(result.funding_volatility, expected_volatility)

    assert math.isclose(result.historical_average, statistics.mean(rates))
    assert result.historical_maximum == max(rates)
    assert result.historical_minimum == min(rates)
    assert result.sample_size == 6
    assert result.confidence_level == 1.0


def test_analyze_falling_series() -> None:
    rates = [0.0006, 0.0005, 0.0004, 0.0003]
    observations = [_obs(h, r) for h, r in enumerate(rates)]
    config = FundingRateAnalysisConfig(trend_window=4, momentum_window=4, volatility_window=4)
    result = FundingRateAnalysisEngine(config).analyze("BTCUSDT", observations)

    assert result.funding_trend == FundingDirection.FALLING
    assert result.funding_trend_value < 0
    assert result.funding_momentum == FundingDirection.FALLING
    assert result.funding_momentum_value < 0


def test_analyze_flat_series() -> None:
    rates = [0.0001, 0.0001, 0.0001, 0.0001]
    observations = [_obs(h, r) for h, r in enumerate(rates)]
    config = FundingRateAnalysisConfig(trend_window=4, momentum_window=4, volatility_window=4)
    result = FundingRateAnalysisEngine(config).analyze("BTCUSDT", observations)

    assert result.funding_trend == FundingDirection.FLAT
    assert math.isclose(result.funding_trend_value, 0.0, abs_tol=1e-15)
    assert result.funding_momentum == FundingDirection.FLAT
    assert result.funding_momentum_value == 0.0
    assert result.funding_volatility == 0.0


def test_analyze_confidence_level_reflects_data_sufficiency() -> None:
    observations = [_obs(h, 0.0001) for h in range(3)]
    result = FundingRateAnalysisEngine().analyze("BTCUSDT", observations)
    assert result.confidence_level == pytest.approx(3 / 30)


def test_analyze_confidence_level_is_capped_at_one() -> None:
    observations = [_obs(h, 0.0001) for h in range(100)]
    result = FundingRateAnalysisEngine().analyze("BTCUSDT", observations)
    assert result.confidence_level == 1.0


def test_analyze_historical_window_limits_historical_stats() -> None:
    rates = [0.0001, 0.0002, 0.0003, 10.0]
    observations = [_obs(h, r) for h, r in enumerate(rates)]
    config = FundingRateAnalysisConfig(historical_window=2)
    result = FundingRateAnalysisEngine(config).analyze("BTCUSDT", observations)
    assert result.historical_maximum == 10.0
    assert result.historical_minimum == 0.0003
    assert math.isclose(result.historical_average, (0.0003 + 10.0) / 2)


def test_analyze_excludes_missing_values() -> None:
    observations = [_obs(0, 0.0001), _obs(1, None), _obs(2, 0.0003)]
    result = FundingRateAnalysisEngine().analyze("BTCUSDT", observations)
    assert result.current_funding == 0.0003
    assert result.previous_funding == 0.0001
    assert result.sample_size == 2


def test_analyze_duplicate_timestamp_keeps_last_given_value() -> None:
    timestamp = datetime(2024, 1, 1, tzinfo=UTC)
    observations = [
        FundingRateObservation(timestamp=timestamp, funding_rate=0.0001),
        FundingRateObservation(timestamp=timestamp, funding_rate=0.0002),
    ]
    result = FundingRateAnalysisEngine().analyze("BTCUSDT", observations)
    assert result.current_funding == 0.0002
    assert result.sample_size == 1


def test_analyze_sorts_out_of_order_observations() -> None:
    observations = [_obs(1, 0.0002), _obs(0, 0.0001)]
    result = FundingRateAnalysisEngine().analyze("BTCUSDT", observations)
    assert result.current_funding == 0.0002
    assert result.previous_funding == 0.0001
    assert result.as_of == datetime(2024, 1, 1, 1, tzinfo=UTC)


def test_validate_delegates_to_funding_data_validator() -> None:
    naive = FundingRateObservation(timestamp=datetime(2024, 1, 1), funding_rate=0.0001)
    issues = FundingRateAnalysisEngine().validate([naive])
    assert any(i.severity == "ERROR" and "timezone-aware" in i.message for i in issues)
