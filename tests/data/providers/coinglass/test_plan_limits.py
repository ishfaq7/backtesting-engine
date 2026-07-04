from datetime import datetime, timedelta, timezone

import pytest

from btengine.data.errors import PlanRestrictionError
from btengine.data.providers.coinglass import plan_limits
from btengine.data.schema import Timeframe

UTC = timezone.utc
START = datetime(2024, 1, 1, tzinfo=UTC)


@pytest.mark.parametrize(
    "timeframe",
    [Timeframe.MIN_1, Timeframe.MIN_5, Timeframe.MIN_15, Timeframe.WEEK_1],
)
def test_unsupported_timeframes_are_rejected(timeframe: Timeframe) -> None:
    assert not plan_limits.is_timeframe_supported(timeframe)
    with pytest.raises(PlanRestrictionError):
        plan_limits.validate_request(timeframe, START, START + timedelta(days=1))


@pytest.mark.parametrize(
    "timeframe",
    [
        Timeframe.MIN_30, Timeframe.HOUR_1, Timeframe.HOUR_2, Timeframe.HOUR_4,
        Timeframe.HOUR_6, Timeframe.HOUR_8, Timeframe.HOUR_12, Timeframe.DAY_1,
    ],
)
def test_supported_timeframes_are_accepted(timeframe: Timeframe) -> None:
    assert plan_limits.is_timeframe_supported(timeframe)
    plan_limits.validate_request(timeframe, START, START + timedelta(hours=1))  # must not raise


def test_daily_timeframe_has_no_history_limit() -> None:
    assert plan_limits.max_history(Timeframe.DAY_1) is None
    plan_limits.validate_request(Timeframe.DAY_1, START, START + timedelta(days=10_000))  # must not raise


@pytest.mark.parametrize(
    "timeframe, max_days",
    [
        (Timeframe.MIN_30, 90),
        (Timeframe.HOUR_1, 180),
        (Timeframe.HOUR_4, 180),
        (Timeframe.HOUR_6, 360),
        (Timeframe.HOUR_12, 360),
    ],
)
def test_max_history_matches_documented_startup_plan_limits(timeframe: Timeframe, max_days: int) -> None:
    assert plan_limits.max_history(timeframe) == timedelta(days=max_days)


def test_request_within_history_limit_is_accepted() -> None:
    plan_limits.validate_request(Timeframe.HOUR_1, START, START + timedelta(days=179))  # must not raise


def test_request_beyond_history_limit_is_rejected() -> None:
    with pytest.raises(PlanRestrictionError) as exc_info:
        plan_limits.validate_request(Timeframe.HOUR_1, START, START + timedelta(days=181))
    assert exc_info.value.plan == "startup"


def test_request_exactly_at_history_limit_is_accepted() -> None:
    plan_limits.validate_request(Timeframe.HOUR_1, START, START + timedelta(days=180))  # must not raise
