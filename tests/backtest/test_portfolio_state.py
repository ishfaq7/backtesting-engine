from datetime import datetime, timezone

import pytest

from btengine.backtest.events import FillEvent, OrderSide
from btengine.backtest.portfolio_state import PortfolioState
from btengine.backtest.position_manager import PositionManager
from btengine.data.schema import Candle, Timeframe

UTC = timezone.utc


def test_initial_state_has_no_pnl() -> None:
    pm = PositionManager()
    ps = PortfolioState(initial_cash=10_000, position_manager=pm)
    assert ps.cash == 10_000
    assert ps.equity == 10_000
    assert ps.unrealized_pnl == 0.0
    assert ps.initial_cash == 10_000


def test_apply_fee_reduces_cash() -> None:
    pm = PositionManager()
    ps = PortfolioState(initial_cash=10_000, position_manager=pm)
    ps.apply_fee(5)
    assert ps.cash == 9_995


def test_apply_realized_pnl_changes_cash() -> None:
    pm = PositionManager()
    ps = PortfolioState(initial_cash=10_000, position_manager=pm)
    ps.apply_realized_pnl(50)
    ps.apply_realized_pnl(-20)
    assert ps.cash == pytest.approx(10_030)


def test_equity_includes_unrealized_pnl_from_open_positions() -> None:
    pm = PositionManager()
    ps = PortfolioState(initial_cash=10_000, position_manager=pm)
    fill = FillEvent(timestamp=datetime(2024, 1, 1, tzinfo=UTC), symbol="BTCUSDT", side=OrderSide.BUY, quantity=1, fill_price=100, fee=0)
    pm.apply_fill(fill)
    candle = Candle(
        exchange="binance", symbol="BTCUSDT", timeframe=Timeframe.HOUR_1,
        timestamp=datetime(2024, 1, 1, 1, tzinfo=UTC), open=105, high=112, low=100, close=110, volume=1,
    )
    pm.mark_to_market(candle)
    assert ps.equity == pytest.approx(10_010)


def test_snapshot_reflects_open_positions_only() -> None:
    pm = PositionManager()
    ps = PortfolioState(initial_cash=10_000, position_manager=pm)
    fill = FillEvent(timestamp=datetime(2024, 1, 1, tzinfo=UTC), symbol="BTCUSDT", side=OrderSide.BUY, quantity=1, fill_price=100, fee=0)
    pm.apply_fill(fill)

    snapshot = ps.snapshot()
    assert snapshot.cash == 10_000
    assert "BTCUSDT" in snapshot.positions
    assert snapshot.positions["BTCUSDT"].quantity == 1
    assert snapshot.positions["BTCUSDT"].avg_entry_price == 100


def test_snapshot_has_no_positions_when_flat() -> None:
    pm = PositionManager()
    ps = PortfolioState(initial_cash=10_000, position_manager=pm)
    snapshot = ps.snapshot()
    assert snapshot.positions == {}
    assert snapshot.equity == 10_000
