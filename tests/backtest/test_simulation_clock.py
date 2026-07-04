from datetime import datetime, timezone

import pytest

from btengine.backtest.errors import ClockError
from btengine.backtest.simulation_clock import SimulationClock

UTC = timezone.utc


def test_requires_timezone_aware_start_time() -> None:
    with pytest.raises(ClockError):
        SimulationClock(datetime(2024, 1, 1))


def test_now_reflects_start_time() -> None:
    clock = SimulationClock(datetime(2024, 1, 1, tzinfo=UTC))
    assert clock.now == datetime(2024, 1, 1, tzinfo=UTC)


def test_advance_to_moves_clock_forward() -> None:
    clock = SimulationClock(datetime(2024, 1, 1, tzinfo=UTC))
    clock.advance_to(datetime(2024, 1, 2, tzinfo=UTC))
    assert clock.now == datetime(2024, 1, 2, tzinfo=UTC)


def test_advance_to_same_time_is_allowed() -> None:
    clock = SimulationClock(datetime(2024, 1, 1, tzinfo=UTC))
    clock.advance_to(datetime(2024, 1, 1, tzinfo=UTC))
    assert clock.now == datetime(2024, 1, 1, tzinfo=UTC)


def test_advance_to_backwards_raises_clock_error() -> None:
    clock = SimulationClock(datetime(2024, 1, 2, tzinfo=UTC))
    with pytest.raises(ClockError):
        clock.advance_to(datetime(2024, 1, 1, tzinfo=UTC))
