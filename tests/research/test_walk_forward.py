from datetime import datetime, timedelta, timezone

import pytest

from btengine.research.errors import ValidationConfigError
from btengine.research.walk_forward import WalkForwardSplitter, WalkForwardWindow

UTC = timezone.utc


def test_constructor_rejects_nonpositive_periods() -> None:
    with pytest.raises(ValidationConfigError):
        WalkForwardSplitter(train_period=timedelta(0), test_period=timedelta(days=1))
    with pytest.raises(ValidationConfigError):
        WalkForwardSplitter(train_period=timedelta(days=1), test_period=timedelta(0))
    with pytest.raises(ValidationConfigError):
        WalkForwardSplitter(train_period=timedelta(days=1), test_period=timedelta(days=1), step=timedelta(0))


def test_split_rejects_naive_datetimes() -> None:
    splitter = WalkForwardSplitter(train_period=timedelta(days=30), test_period=timedelta(days=10))
    with pytest.raises(ValidationConfigError):
        splitter.split(datetime(2024, 1, 1), datetime(2024, 6, 1, tzinfo=UTC))


def test_split_rejects_start_after_end() -> None:
    splitter = WalkForwardSplitter(train_period=timedelta(days=30), test_period=timedelta(days=10))
    with pytest.raises(ValidationConfigError):
        splitter.split(datetime(2024, 6, 1, tzinfo=UTC), datetime(2024, 1, 1, tzinfo=UTC))


def test_produces_expected_rolling_windows() -> None:
    # default step == test_period (10 days), so each window slides 10 days
    # forward while train_start..train_end stays a fixed 30-day span.
    splitter = WalkForwardSplitter(train_period=timedelta(days=30), test_period=timedelta(days=10))
    start = datetime(2024, 1, 1, tzinfo=UTC)
    end = start + timedelta(days=80)  # last full window's test_end lands exactly on day 80

    windows = splitter.split(start, end)

    assert windows == [
        WalkForwardWindow(
            train_start=start + timedelta(days=10 * i),
            train_end=start + timedelta(days=10 * i + 30),
            test_start=start + timedelta(days=10 * i + 30),
            test_end=start + timedelta(days=10 * i + 40),
        )
        for i in range(5)
    ]


def test_default_step_equals_test_period_giving_nonoverlapping_test_windows() -> None:
    splitter = WalkForwardSplitter(train_period=timedelta(days=30), test_period=timedelta(days=10))
    start = datetime(2024, 1, 1, tzinfo=UTC)
    windows = splitter.split(start, start + timedelta(days=100))
    for first, second in zip(windows, windows[1:]):
        assert second.test_start == first.test_end


def test_custom_step_can_overlap_or_skip() -> None:
    splitter = WalkForwardSplitter(train_period=timedelta(days=30), test_period=timedelta(days=10), step=timedelta(days=20))
    start = datetime(2024, 1, 1, tzinfo=UTC)
    windows = splitter.split(start, start + timedelta(days=100))
    assert all(w.train_start == start + timedelta(days=20 * i) for i, w in enumerate(windows))


def test_incomplete_trailing_window_is_dropped() -> None:
    splitter = WalkForwardSplitter(train_period=timedelta(days=30), test_period=timedelta(days=10))
    start = datetime(2024, 1, 1, tzinfo=UTC)
    # only enough room for the train period + a partial test period
    end = start + timedelta(days=35)
    windows = splitter.split(start, end)
    assert windows == []


def test_range_too_short_for_any_window_returns_empty_list() -> None:
    splitter = WalkForwardSplitter(train_period=timedelta(days=30), test_period=timedelta(days=10))
    start = datetime(2024, 1, 1, tzinfo=UTC)
    windows = splitter.split(start, start + timedelta(days=5))
    assert windows == []
