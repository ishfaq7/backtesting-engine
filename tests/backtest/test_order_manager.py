from datetime import datetime, timezone

import pytest

from btengine.backtest.events import FillEvent, OrderSide, SignalAction, SignalEvent
from btengine.backtest.order_manager import OrderManager
from btengine.backtest.position_manager import PositionManager
from btengine.data.schema import Candle, Timeframe

UTC = timezone.utc


def _signal(action: SignalAction, quantity: float | None = None, symbol: str = "BTCUSDT") -> SignalEvent:
    return SignalEvent(timestamp=datetime(2024, 1, 1, tzinfo=UTC), symbol=symbol, action=action, quantity=quantity)


def _candle(hour: int, open_price: float) -> Candle:
    return Candle(
        exchange="binance", symbol="BTCUSDT", timeframe=Timeframe.HOUR_1,
        timestamp=datetime(2024, 1, 1, hour, tzinfo=UTC), open=open_price, high=open_price + 5,
        low=open_price - 5, close=open_price, volume=1,
    )


def _manager(fee_rate: float = 0.0, slippage_bps: float = 0.0) -> OrderManager:
    return OrderManager(known_symbols={"BTCUSDT"}, fee_rate=fee_rate, slippage_bps=slippage_bps)


def test_constructor_rejects_negative_fee_or_slippage() -> None:
    with pytest.raises(ValueError):
        OrderManager(known_symbols={"BTCUSDT"}, fee_rate=-0.1, slippage_bps=0)
    with pytest.raises(ValueError):
        OrderManager(known_symbols={"BTCUSDT"}, fee_rate=0, slippage_bps=-1)


def test_unknown_symbol_is_rejected() -> None:
    manager = _manager()
    order = manager.validate_signal(_signal(SignalAction.ENTER_LONG, 1, symbol="ETHUSDT"), PositionManager())
    assert order is None


def test_enter_long_produces_buy_order() -> None:
    manager = _manager()
    order = manager.validate_signal(_signal(SignalAction.ENTER_LONG, 1.5), PositionManager())
    assert order is not None
    assert order.side == OrderSide.BUY
    assert order.quantity == 1.5


def test_enter_short_produces_sell_order() -> None:
    manager = _manager()
    order = manager.validate_signal(_signal(SignalAction.ENTER_SHORT, 2), PositionManager())
    assert order.side == OrderSide.SELL


@pytest.mark.parametrize("quantity", [None, 0, -1])
def test_entry_without_positive_quantity_is_rejected(quantity: float | None) -> None:
    manager = _manager()
    order = manager.validate_signal(_signal(SignalAction.ENTER_LONG, quantity), PositionManager())
    assert order is None


def test_exit_without_open_position_is_rejected() -> None:
    manager = _manager()
    order = manager.validate_signal(_signal(SignalAction.EXIT), PositionManager())
    assert order is None


def test_exit_produces_opposite_side_order_for_long_position() -> None:
    manager = _manager()
    pm = PositionManager()
    pm.apply_fill(FillEvent(timestamp=datetime(2024, 1, 1, tzinfo=UTC), symbol="BTCUSDT", side=OrderSide.BUY, quantity=2, fill_price=100, fee=0))
    order = manager.validate_signal(_signal(SignalAction.EXIT), pm)
    assert order.side == OrderSide.SELL
    assert order.quantity == 2


def test_exit_produces_opposite_side_order_for_short_position() -> None:
    manager = _manager()
    pm = PositionManager()
    pm.apply_fill(FillEvent(timestamp=datetime(2024, 1, 1, tzinfo=UTC), symbol="BTCUSDT", side=OrderSide.SELL, quantity=1, fill_price=100, fee=0))
    order = manager.validate_signal(_signal(SignalAction.EXIT), pm)
    assert order.side == OrderSide.BUY
    assert order.quantity == 1


def test_orders_are_not_filled_until_next_bar() -> None:
    manager = _manager()
    order = manager.validate_signal(_signal(SignalAction.ENTER_LONG, 1), PositionManager())
    manager.queue_pending(order)
    assert manager.has_pending_orders
    fills = manager.execute_pending_orders(symbol="BTCUSDT", bar=_candle(1, 105))
    assert len(fills) == 1
    assert fills[0].fill_price == 105
    assert not manager.has_pending_orders


def test_execute_pending_orders_for_other_symbol_does_not_touch_unrelated_orders() -> None:
    manager = OrderManager(known_symbols={"BTCUSDT", "ETHUSDT"}, fee_rate=0, slippage_bps=0)
    order = manager.validate_signal(_signal(SignalAction.ENTER_LONG, 1, symbol="ETHUSDT"), PositionManager())
    manager.queue_pending(order)
    fills = manager.execute_pending_orders(symbol="BTCUSDT", bar=_candle(1, 105))
    assert fills == []
    assert manager.has_pending_orders  # ETHUSDT order still pending


def test_fee_rate_is_applied_to_fill() -> None:
    manager = _manager(fee_rate=0.001)
    order = manager.validate_signal(_signal(SignalAction.ENTER_LONG, 2), PositionManager())
    manager.queue_pending(order)
    fills = manager.execute_pending_orders(symbol="BTCUSDT", bar=_candle(1, 100))
    assert fills[0].fee == pytest.approx(100 * 2 * 0.001)


def test_slippage_increases_buy_price_and_decreases_sell_price() -> None:
    manager = _manager(slippage_bps=100)  # 1%
    buy_order = manager.validate_signal(_signal(SignalAction.ENTER_LONG, 1), PositionManager())
    manager.queue_pending(buy_order)
    buy_fills = manager.execute_pending_orders(symbol="BTCUSDT", bar=_candle(1, 100))
    assert buy_fills[0].fill_price == pytest.approx(101.0)

    pm = PositionManager()
    pm.apply_fill(FillEvent(timestamp=datetime(2024, 1, 1, tzinfo=UTC), symbol="BTCUSDT", side=OrderSide.BUY, quantity=1, fill_price=100, fee=0))
    sell_order = manager.validate_signal(_signal(SignalAction.EXIT), pm)
    manager.queue_pending(sell_order)
    sell_fills = manager.execute_pending_orders(symbol="BTCUSDT", bar=_candle(2, 100))
    assert sell_fills[0].fill_price == pytest.approx(99.0)


def test_unrecognized_action_is_rejected() -> None:
    manager = _manager()
    # Construct a SignalEvent bypassing the enum to simulate an unexpected value.
    bad_signal = SignalEvent(timestamp=datetime(2024, 1, 1, tzinfo=UTC), symbol="BTCUSDT", action="NOT_REAL")  # type: ignore[arg-type]
    assert manager.validate_signal(bad_signal, PositionManager()) is None
