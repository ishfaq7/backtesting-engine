from datetime import datetime, timezone

from btengine.backtest.event_loop import EventLoop
from btengine.backtest.events import Event

UTC = timezone.utc


def test_empty_loop_pop_returns_none() -> None:
    loop = EventLoop()
    assert loop.pop() is None
    assert loop.is_empty()
    assert len(loop) == 0


def test_events_pop_in_fifo_order() -> None:
    loop = EventLoop()
    e1 = Event(timestamp=datetime(2024, 1, 1, tzinfo=UTC))
    e2 = Event(timestamp=datetime(2024, 1, 2, tzinfo=UTC))
    loop.push(e1)
    loop.push(e2)
    assert len(loop) == 2
    assert loop.pop() is e1
    assert loop.pop() is e2
    assert loop.is_empty()
