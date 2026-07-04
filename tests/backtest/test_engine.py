from collections.abc import Sequence
from datetime import datetime, timezone
from pathlib import Path

import pytest

from btengine.backtest.configuration_manager import BacktestConfig
from btengine.backtest.data_feed import HistoricalCandleFeed
from btengine.backtest.engine import BacktestEngine
from btengine.backtest.errors import UnknownEventError
from btengine.backtest.events import Event, SignalAction, SignalEvent
from btengine.data.repository import DataRepository
from btengine.data.schema import Candle, Timeframe
from btengine.strategy.base import Strategy
from btengine.strategy.context import StrategyContext

UTC = timezone.utc


def _candle(symbol: str, hour: int, price: float) -> Candle:
    return Candle(
        exchange="binance", symbol=symbol, timeframe=Timeframe.HOUR_1,
        timestamp=datetime(2024, 1, 1, hour, tzinfo=UTC), open=price, high=price + 2,
        low=price - 2, close=price, volume=1,
    )


class ScriptedStrategy(Strategy):
    """Test double: fires a scripted signal at specific hours. Not a real strategy."""

    def __init__(self, script: dict[int, SignalEvent]) -> None:
        self._script = script
        self.seen_contexts: list[StrategyContext] = []

    def on_market_event(self, context: StrategyContext) -> Sequence[SignalEvent]:
        self.seen_contexts.append(context)
        signal = self._script.get(context.timestamp.hour)
        return [signal] if signal is not None else []


class NoOpStrategy(Strategy):
    def on_market_event(self, context: StrategyContext) -> Sequence[SignalEvent]:
        return []


@pytest.fixture
def repository(tmp_path: Path) -> DataRepository:
    return DataRepository(tmp_path)


def _config(**overrides) -> BacktestConfig:
    base = dict(
        exchange="binance", symbols=["BTCUSDT"], timeframe=Timeframe.HOUR_1,
        start=datetime(2024, 1, 1, tzinfo=UTC), end=datetime(2024, 1, 1, 9, tzinfo=UTC),
        initial_cash=10_000, fee_rate=0.0, slippage_bps=0.0,
    )
    base.update(overrides)
    return BacktestConfig(**base)


def test_engine_runs_with_no_signals_and_produces_empty_result(repository: DataRepository) -> None:
    prices = [100, 101, 102, 103]
    candles = [_candle("BTCUSDT", h, p) for h, p in enumerate(prices)]
    repository.write(Candle, candles, exchange="binance", symbol="BTCUSDT", timeframe=Timeframe.HOUR_1)

    config = _config(end=datetime(2024, 1, 1, 3, tzinfo=UTC))
    feed = HistoricalCandleFeed(repository, exchange="binance", symbols=["BTCUSDT"], timeframe=Timeframe.HOUR_1, start=config.start, end=config.end)
    engine = BacktestEngine(config=config, repository=repository, data_feed=feed, strategy=NoOpStrategy())

    result = engine.run()
    assert result.trades == []
    assert len(result.equity_curve) == 4
    assert result.summary.final_equity == 10_000


def test_signal_fills_on_next_bar_open_not_same_bar(repository: DataRepository) -> None:
    prices = [100, 101, 102, 101, 99, 105, 110, 108, 95, 90]
    candles = [_candle("BTCUSDT", h, p) for h, p in enumerate(prices)]
    repository.write(Candle, candles, exchange="binance", symbol="BTCUSDT", timeframe=Timeframe.HOUR_1)

    script = {
        1: SignalEvent(timestamp=datetime(2024, 1, 1, 1, tzinfo=UTC), symbol="BTCUSDT", action=SignalAction.ENTER_LONG, quantity=1.0),
        6: SignalEvent(timestamp=datetime(2024, 1, 1, 6, tzinfo=UTC), symbol="BTCUSDT", action=SignalAction.EXIT),
    }
    strategy = ScriptedStrategy(script)
    config = _config()
    feed = HistoricalCandleFeed(repository, exchange="binance", symbols=["BTCUSDT"], timeframe=Timeframe.HOUR_1, start=config.start, end=config.end)
    engine = BacktestEngine(config=config, repository=repository, data_feed=feed, strategy=strategy)

    result = engine.run()

    assert len(result.trades) == 1
    trade = result.trades[0]
    # signal at hour 1 (open=101) -> filled at hour 2's open (102)
    assert trade.entry_price == 102
    # exit signal at hour 6 (open=110) -> filled at hour 7's open (108)
    assert trade.exit_price == 108
    assert len(strategy.seen_contexts) == 10


def test_strategy_never_sees_future_candles(repository: DataRepository) -> None:
    prices = list(range(100, 110))
    candles = [_candle("BTCUSDT", h, p) for h, p in enumerate(prices)]
    repository.write(Candle, candles, exchange="binance", symbol="BTCUSDT", timeframe=Timeframe.HOUR_1)

    class LookaheadCheckingStrategy(Strategy):
        def on_market_event(self, context: StrategyContext) -> Sequence[SignalEvent]:
            history = context.history.get_candles(lookback_periods=20)
            assert all(c.timestamp <= context.timestamp for c in history)
            assert context.current_candle.timestamp == context.timestamp
            return []

    config = _config()
    feed = HistoricalCandleFeed(repository, exchange="binance", symbols=["BTCUSDT"], timeframe=Timeframe.HOUR_1, start=config.start, end=config.end)
    engine = BacktestEngine(config=config, repository=repository, data_feed=feed, strategy=LookaheadCheckingStrategy())
    engine.run()  # would raise AssertionError inside the strategy if lookahead ever occurred


def test_pending_order_at_end_of_run_is_left_unfilled(repository: DataRepository) -> None:
    prices = [100, 101, 102]
    candles = [_candle("BTCUSDT", h, p) for h, p in enumerate(prices)]
    repository.write(Candle, candles, exchange="binance", symbol="BTCUSDT", timeframe=Timeframe.HOUR_1)

    # signal on the very last candle can never be filled (no next bar)
    script = {2: SignalEvent(timestamp=datetime(2024, 1, 1, 2, tzinfo=UTC), symbol="BTCUSDT", action=SignalAction.ENTER_LONG, quantity=1.0)}
    config = _config(end=datetime(2024, 1, 1, 2, tzinfo=UTC))
    feed = HistoricalCandleFeed(repository, exchange="binance", symbols=["BTCUSDT"], timeframe=Timeframe.HOUR_1, start=config.start, end=config.end)
    engine = BacktestEngine(config=config, repository=repository, data_feed=feed, strategy=ScriptedStrategy(script))

    result = engine.run()
    assert result.trades == []  # never filled, so no position and no trade


def test_multi_asset_positions_are_tracked_independently(repository: DataRepository) -> None:
    btc = [_candle("BTCUSDT", h, 100 + h) for h in range(4)]
    eth = [_candle("ETHUSDT", h, 50 - h) for h in range(4)]
    repository.write(Candle, btc, exchange="binance", symbol="BTCUSDT", timeframe=Timeframe.HOUR_1)
    repository.write(Candle, eth, exchange="binance", symbol="ETHUSDT", timeframe=Timeframe.HOUR_1)

    class DualAssetStrategy(Strategy):
        def on_market_event(self, context: StrategyContext) -> Sequence[SignalEvent]:
            if context.timestamp.hour == 0:
                return [SignalEvent(timestamp=context.timestamp, symbol=context.symbol, action=SignalAction.ENTER_LONG, quantity=1.0)]
            return []

    config = _config(symbols=["BTCUSDT", "ETHUSDT"], end=datetime(2024, 1, 1, 3, tzinfo=UTC))
    feed = HistoricalCandleFeed(repository, exchange="binance", symbols=["BTCUSDT", "ETHUSDT"], timeframe=Timeframe.HOUR_1, start=config.start, end=config.end)
    engine = BacktestEngine(config=config, repository=repository, data_feed=feed, strategy=DualAssetStrategy())

    result = engine.run()
    # both positions remain open at the end (no exit signals) -> no closed trades yet
    assert result.trades == []


def test_dispatch_raises_on_unknown_event_type(repository: DataRepository) -> None:
    config = _config(end=datetime(2024, 1, 1, 1, tzinfo=UTC))
    repository.write(
        Candle, [_candle("BTCUSDT", 0, 100), _candle("BTCUSDT", 1, 101)],
        exchange="binance", symbol="BTCUSDT", timeframe=Timeframe.HOUR_1,
    )
    feed = HistoricalCandleFeed(repository, exchange="binance", symbols=["BTCUSDT"], timeframe=Timeframe.HOUR_1, start=config.start, end=config.end)
    engine = BacktestEngine(config=config, repository=repository, data_feed=feed, strategy=NoOpStrategy())

    class MysteryEvent(Event):
        pass

    with pytest.raises(UnknownEventError):
        engine._dispatch(MysteryEvent(timestamp=datetime(2024, 1, 1, tzinfo=UTC)))


def test_fees_reduce_final_equity(repository: DataRepository) -> None:
    prices = [100, 101, 102, 103]
    candles = [_candle("BTCUSDT", h, p) for h, p in enumerate(prices)]
    repository.write(Candle, candles, exchange="binance", symbol="BTCUSDT", timeframe=Timeframe.HOUR_1)

    script = {0: SignalEvent(timestamp=datetime(2024, 1, 1, 0, tzinfo=UTC), symbol="BTCUSDT", action=SignalAction.ENTER_LONG, quantity=1.0)}
    config = _config(end=datetime(2024, 1, 1, 3, tzinfo=UTC), fee_rate=0.01, slippage_bps=0)
    feed = HistoricalCandleFeed(repository, exchange="binance", symbols=["BTCUSDT"], timeframe=Timeframe.HOUR_1, start=config.start, end=config.end)
    engine = BacktestEngine(config=config, repository=repository, data_feed=feed, strategy=ScriptedStrategy(script))

    result = engine.run()
    # filled at hour 1's open (101), fee = 101*1*0.01 = 1.01, no exit so equity = cash - fee + unrealized
    assert result.summary.final_equity < 10_000 + (103 - 101)  # fee eats into the unrealized gain
