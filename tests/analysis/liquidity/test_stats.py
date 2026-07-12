import math
from datetime import datetime, timedelta, timezone

import pytest

from btengine.analysis.liquidity.config import AggregationMethod
from btengine.analysis.liquidity.stats import (
    aggregate_by_timestamp,
    align_two_series,
    compute_bias,
    half_split_delta,
    zscore_of_latest,
)

UTC = timezone.utc


def _ts(hour: int) -> datetime:
    return datetime(2024, 1, 1, tzinfo=UTC) + timedelta(hours=hour)


# --- compute_bias ----------------------------------------------------------


def test_compute_bias_positive_when_long_larger() -> None:
    assert compute_bias(150.0, 50.0) == 0.5


def test_compute_bias_negative_when_short_larger() -> None:
    assert compute_bias(50.0, 150.0) == -0.5


def test_compute_bias_zero_when_equal() -> None:
    assert compute_bias(100.0, 100.0) == 0.0


def test_compute_bias_none_when_both_zero() -> None:
    assert compute_bias(0.0, 0.0) is None


# --- aggregate_by_timestamp --------------------------------------------------


def test_aggregate_sum_combines_same_timestamp_readings() -> None:
    readings = [(_ts(0), 10.0), (_ts(0), 20.0), (_ts(1), 5.0)]
    result = aggregate_by_timestamp(readings, AggregationMethod.SUM)
    assert result == [(_ts(0), 30.0), (_ts(1), 5.0)]


def test_aggregate_mean_combines_same_timestamp_readings() -> None:
    readings = [(_ts(0), 10.0), (_ts(0), 20.0), (_ts(1), 5.0)]
    result = aggregate_by_timestamp(readings, AggregationMethod.MEAN)
    assert result == [(_ts(0), 15.0), (_ts(1), 5.0)]


def test_aggregate_sorts_by_timestamp() -> None:
    readings = [(_ts(1), 5.0), (_ts(0), 10.0)]
    result = aggregate_by_timestamp(readings, AggregationMethod.SUM)
    assert [ts for ts, _ in result] == [_ts(0), _ts(1)]


def test_aggregate_handles_empty_input() -> None:
    assert aggregate_by_timestamp([], AggregationMethod.SUM) == []


def test_aggregate_rejects_unsupported_method() -> None:
    with pytest.raises(NotImplementedError):
        aggregate_by_timestamp([(_ts(0), 1.0)], "UNSUPPORTED")  # type: ignore[arg-type]


# --- zscore_of_latest --------------------------------------------------------


def test_zscore_of_latest_computes_expected_value() -> None:
    values = [1.0, 2.0, 3.0, 10.0]
    baseline = values[:-1]
    import statistics

    expected = (10.0 - statistics.mean(baseline)) / statistics.stdev(baseline)
    assert zscore_of_latest(values) == pytest.approx(expected)


def test_zscore_of_latest_none_with_fewer_than_two_values() -> None:
    assert zscore_of_latest([1.0]) is None
    assert zscore_of_latest([]) is None


def test_zscore_of_latest_none_with_fewer_than_two_baseline_values() -> None:
    assert zscore_of_latest([1.0, 2.0]) is None


def test_zscore_of_latest_none_when_baseline_stdev_is_zero() -> None:
    assert zscore_of_latest([5.0, 5.0, 5.0, 5.0]) is None


# --- half_split_delta ---------------------------------------------------------


def test_half_split_delta_positive_when_rising() -> None:
    assert half_split_delta([1.0, 2.0, 3.0, 4.0]) == 2.0


def test_half_split_delta_negative_when_falling() -> None:
    assert half_split_delta([4.0, 3.0, 2.0, 1.0]) == -2.0


def test_half_split_delta_none_with_fewer_than_two_values() -> None:
    assert half_split_delta([1.0]) is None
    assert half_split_delta([]) is None


def test_half_split_delta_handles_odd_length() -> None:
    # midpoint=1 -> first_half=[1.0], second_half=[2.0,3.0] (mean=2.5)
    assert half_split_delta([1.0, 2.0, 3.0]) == 1.5


# --- align_two_series ----------------------------------------------------------


def test_align_two_series_inner_joins_on_shared_timestamps() -> None:
    primary = [(_ts(0), 1.0), (_ts(1), 2.0), (_ts(2), 3.0)]
    secondary = [(_ts(1), 100.0), (_ts(2), 200.0), (_ts(3), 300.0)]
    result = align_two_series(primary, secondary)
    assert result == [(_ts(1), 2.0, 100.0), (_ts(2), 3.0, 200.0)]


def test_align_two_series_handles_no_overlap() -> None:
    primary = [(_ts(0), 1.0)]
    secondary = [(_ts(1), 100.0)]
    assert align_two_series(primary, secondary) == []


def test_align_two_series_handles_empty_input() -> None:
    assert align_two_series([], []) == []
