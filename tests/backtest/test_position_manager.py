from datetime import datetime, timezone

import pytest

from btengine.backtest.events import FillEvent, OrderSide
from btengine.backtest.position_manager import PositionManager
from btengine.data.schema import Candle, Timeframe

UTC = timezone.utc


def _fill(side: OrderSide, quantity: float, price: float, hour: int = 0, fee: float = 0.0) -> FillEvent:
    return FillEvent(
        timestamp=datetime(2024, 1, 1, hour, tzinfo=UTC),
        symbol="BTCUSDT",
        side=side,
        quantity=quantity,
        fill_price=price,
        fee=fee,
    )


def test_opening_a_position_has_no_realized_pnl() -> None:
    pm = PositionManager()
    pnl, closed = pm.apply_fill(_fill(OrderSide.BUY, 1, 100))
    assert pnl == 0.0
    assert closed is None
    position = pm.get_position("BTCUSDT")
    assert position is not None
    assert position.quantity == 1
    assert position.avg_entry_price == 100
    assert position.side == "LONG"


def test_get_position_returns_none_when_flat() -> None:
    pm = PositionManager()
    assert pm.get_position("BTCUSDT") is None


def test_flat_position_side_is_flat() -> None:
    from btengine.backtest.position_manager import Position

    position = Position(symbol="BTCUSDT")
    assert position.side == "FLAT"
    assert position.is_open is False


def test_extending_a_position_updates_weighted_average_price() -> None:
    pm = PositionManager()
    pm.apply_fill(_fill(OrderSide.BUY, 1, 100))
    pm.apply_fill(_fill(OrderSide.BUY, 1, 110))
    position = pm.get_position("BTCUSDT")
    assert position.quantity == 2
    assert position.avg_entry_price == pytest.approx(105.0)


def test_fully_closing_a_long_position_realizes_pnl() -> None:
    pm = PositionManager()
    pm.apply_fill(_fill(OrderSide.BUY, 1, 100))
    pnl, closed = pm.apply_fill(_fill(OrderSide.SELL, 1, 120, hour=1, fee=0.5))
    assert pnl == pytest.approx(20.0)
    assert closed is not None
    assert closed.side == "LONG"
    assert closed.quantity == 1
    assert closed.entry_price == 100
    assert closed.exit_price == 120
    assert closed.fee == 0.5
    assert pm.get_position("BTCUSDT") is None


def test_partially_closing_keeps_position_open_at_same_entry_price() -> None:
    pm = PositionManager()
    pm.apply_fill(_fill(OrderSide.BUY, 1, 100))
    pnl, closed = pm.apply_fill(_fill(OrderSide.SELL, 0.4, 110, hour=1))
    assert pnl == pytest.approx(4.0)
    assert closed.quantity == pytest.approx(0.4)
    position = pm.get_position("BTCUSDT")
    assert position.quantity == pytest.approx(0.6)
    assert position.avg_entry_price == 100  # unchanged for the still-open portion


def test_overshooting_fill_flips_position_direction() -> None:
    pm = PositionManager()
    pm.apply_fill(_fill(OrderSide.BUY, 1, 100))
    pnl, closed = pm.apply_fill(_fill(OrderSide.SELL, 1.5, 90, hour=1))
    assert pnl == pytest.approx((90 - 100) * 1)  # only the closing 1.0 realizes pnl
    assert closed.quantity == 1
    position = pm.get_position("BTCUSDT")
    assert position.quantity == pytest.approx(-0.5)
    assert position.avg_entry_price == 90
    assert position.side == "SHORT"


def test_short_position_profits_when_price_falls() -> None:
    pm = PositionManager()
    pm.apply_fill(_fill(OrderSide.SELL, 1, 100))  # open short
    pnl, closed = pm.apply_fill(_fill(OrderSide.BUY, 1, 80, hour=1))  # cover
    assert pnl == pytest.approx(20.0)
    assert closed.side == "SHORT"


def test_mark_to_market_updates_unrealized_pnl_for_long() -> None:
    pm = PositionManager()
    pm.apply_fill(_fill(OrderSide.BUY, 1, 100))
    candle = Candle(
        exchange="binance", symbol="BTCUSDT", timeframe=Timeframe.HOUR_1,
        timestamp=datetime(2024, 1, 1, 1, tzinfo=UTC), open=105, high=112, low=100, close=110, volume=1,
    )
    pm.mark_to_market(candle)
    assert pm.get_position("BTCUSDT").unrealized_pnl == pytest.approx(10.0)


def test_mark_to_market_is_a_noop_when_flat() -> None:
    pm = PositionManager()
    candle = Candle(
        exchange="binance", symbol="BTCUSDT", timeframe=Timeframe.HOUR_1,
        timestamp=datetime(2024, 1, 1, tzinfo=UTC), open=100, high=101, low=99, close=100, volume=1,
    )
    pm.mark_to_market(candle)  # should not raise
    assert pm.get_position("BTCUSDT") is None


def test_positions_property_excludes_flat_symbols() -> None:
    pm = PositionManager()
    pm.apply_fill(_fill(OrderSide.BUY, 1, 100))
    pm.apply_fill(_fill(OrderSide.SELL, 1, 110, hour=1))  # closes fully -> flat
    assert pm.positions == {}
