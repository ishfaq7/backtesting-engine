from datetime import datetime, timezone
from pathlib import Path

import pytest

from btengine.data.repository import DataRepository
from btengine.data.schema import Candle, Timeframe
from btengine.strategy.context import HistoryView, PortfolioSnapshot, PositionSnapshot, StrategyContext

UTC = timezone.utc


class FakeClock:
    def __init__(self, now: datetime) -> None:
        self.now = now


def _candle(hour: int) -> Candle:
    return Candle(
        exchange="binance", symbol="BTCUSDT", timeframe=Timeframe.HOUR_1,
        timestamp=datetime(2024, 1, 1, hour, tzinfo=UTC), open=100, high=101, low=99, close=100, volume=1,
    )


@pytest.fixture
def repository(tmp_path: Path) -> DataRepository:
    repo = DataRepository(tmp_path)
    repo.write(Candle, [_candle(h) for h in range(10)], exchange="binance", symbol="BTCUSDT", timeframe=Timeframe.HOUR_1)
    return repo


def test_get_candles_with_lookback_periods(repository: DataRepository) -> None:
    clock = FakeClock(datetime(2024, 1, 1, 5, tzinfo=UTC))
    history = HistoryView(repository, clock, exchange="binance", symbol="BTCUSDT", timeframe=Timeframe.HOUR_1)
    result = history.get_candles(lookback_periods=3)
    assert [c.timestamp.hour for c in result] == [2, 3, 4, 5]


def test_get_candles_never_returns_data_beyond_now(repository: DataRepository) -> None:
    clock = FakeClock(datetime(2024, 1, 1, 3, tzinfo=UTC))
    history = HistoryView(repository, clock, exchange="binance", symbol="BTCUSDT", timeframe=Timeframe.HOUR_1)
    # explicitly ask for a start far in the past and rely on the implicit end=now cap
    result = history.get_candles(start=datetime(2024, 1, 1, 0, tzinfo=UTC))
    assert max(c.timestamp for c in result) <= clock.now
    assert [c.timestamp.hour for c in result] == [0, 1, 2, 3]


def test_get_candles_clamps_start_after_now_to_now(repository: DataRepository) -> None:
    clock = FakeClock(datetime(2024, 1, 1, 2, tzinfo=UTC))
    history = HistoryView(repository, clock, exchange="binance", symbol="BTCUSDT", timeframe=Timeframe.HOUR_1)
    result = history.get_candles(start=datetime(2024, 1, 1, 9, tzinfo=UTC))  # "future" start request
    assert all(c.timestamp <= clock.now for c in result)


def test_get_candles_requires_start_or_lookback(repository: DataRepository) -> None:
    clock = FakeClock(datetime(2024, 1, 1, 2, tzinfo=UTC))
    history = HistoryView(repository, clock, exchange="binance", symbol="BTCUSDT", timeframe=Timeframe.HOUR_1)
    with pytest.raises(ValueError):
        history.get_candles()


def test_get_candles_rejects_nonpositive_lookback(repository: DataRepository) -> None:
    clock = FakeClock(datetime(2024, 1, 1, 2, tzinfo=UTC))
    history = HistoryView(repository, clock, exchange="binance", symbol="BTCUSDT", timeframe=Timeframe.HOUR_1)
    with pytest.raises(ValueError):
        history.get_candles(lookback_periods=0)


def test_strategy_context_is_frozen_and_holds_expected_fields(repository: DataRepository) -> None:
    clock = FakeClock(datetime(2024, 1, 1, 2, tzinfo=UTC))
    history = HistoryView(repository, clock, exchange="binance", symbol="BTCUSDT", timeframe=Timeframe.HOUR_1)
    snapshot = PortfolioSnapshot(cash=100, equity=100, positions={})
    context = StrategyContext(
        timestamp=clock.now, exchange="BINANCE", symbol="BTCUSDT",
        current_candle=_candle(2), history=history, portfolio=snapshot,
    )
    assert context.symbol == "BTCUSDT"
    assert context.portfolio.equity == 100
    with pytest.raises(Exception):
        context.symbol = "ETHUSDT"  # type: ignore[misc]


def test_position_snapshot_is_immutable() -> None:
    snapshot = PositionSnapshot(symbol="BTCUSDT", quantity=1, avg_entry_price=100, unrealized_pnl=0)
    with pytest.raises(Exception):
        snapshot.quantity = 2  # type: ignore[misc]
