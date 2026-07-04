from datetime import datetime, timezone

from btengine.backtest.events import (
    Event,
    FillEvent,
    MarketEvent,
    OrderEvent,
    OrderSide,
    SignalAction,
    SignalEvent,
)
from btengine.data.schema import Candle, Timeframe

UTC = timezone.utc


def _candle() -> Candle:
    return Candle(
        exchange="binance",
        symbol="btcusdt",
        timeframe=Timeframe.HOUR_1,
        timestamp=datetime(2024, 1, 1, tzinfo=UTC),
        open=100,
        high=101,
        low=99,
        close=100,
        volume=1,
    )


def test_market_event_from_candle_derives_fields() -> None:
    candle = _candle()
    event = MarketEvent.from_candle(candle)
    assert isinstance(event, Event)
    assert event.timestamp == candle.timestamp
    assert event.exchange == "BINANCE"
    assert event.symbol == "BTCUSDT"
    assert event.candle is candle


def test_signal_event_defaults() -> None:
    signal = SignalEvent(timestamp=_candle().timestamp, symbol="BTCUSDT", action=SignalAction.EXIT)
    assert signal.quantity is None
    assert signal.metadata == {}


def test_order_and_fill_events_are_immutable() -> None:
    order = OrderEvent(timestamp=_candle().timestamp, symbol="BTCUSDT", side=OrderSide.BUY, quantity=1.0)
    fill = FillEvent(
        timestamp=_candle().timestamp, symbol="BTCUSDT", side=OrderSide.BUY, quantity=1.0, fill_price=100, fee=0.1
    )
    try:
        order.quantity = 2.0  # type: ignore[misc]
        assert False, "expected FrozenInstanceError"
    except Exception:
        pass
    try:
        fill.fee = 0.0  # type: ignore[misc]
        assert False, "expected FrozenInstanceError"
    except Exception:
        pass
