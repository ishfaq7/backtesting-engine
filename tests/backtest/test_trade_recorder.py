from datetime import datetime, timezone

from btengine.backtest.position_manager import ClosedTrade
from btengine.backtest.trade_recorder import TradeRecorder

UTC = timezone.utc


def _trade(pnl: float) -> ClosedTrade:
    return ClosedTrade(
        symbol="BTCUSDT", side="LONG", quantity=1, entry_price=100, exit_price=100 + pnl,
        exit_time=datetime(2024, 1, 1, tzinfo=UTC), realized_pnl=pnl, fee=0.1,
    )


def test_starts_empty() -> None:
    recorder = TradeRecorder()
    assert len(recorder) == 0
    assert recorder.trades == []


def test_records_trades_in_order() -> None:
    recorder = TradeRecorder()
    t1, t2 = _trade(10), _trade(-5)
    recorder.record(t1)
    recorder.record(t2)
    assert recorder.trades == [t1, t2]
    assert len(recorder) == 2


def test_trades_property_returns_a_copy() -> None:
    recorder = TradeRecorder()
    recorder.record(_trade(1))
    trades = recorder.trades
    trades.append(_trade(2))
    assert len(recorder) == 1
