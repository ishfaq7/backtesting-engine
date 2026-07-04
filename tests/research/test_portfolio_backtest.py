from collections.abc import Sequence
from datetime import datetime, timezone
from pathlib import Path

import pytest

from btengine.backtest.configuration_manager import BacktestConfig
from btengine.backtest.events import SignalAction, SignalEvent
from btengine.data.repository import DataRepository
from btengine.data.schema import Candle, Timeframe
from btengine.research.portfolio_backtest import PortfolioBacktestRunner
from btengine.strategy.base import Strategy
from btengine.strategy.context import StrategyContext

UTC = timezone.utc


def _candle(symbol: str, hour: int, price: float) -> Candle:
    return Candle(
        exchange="binance", symbol=symbol, timeframe=Timeframe.HOUR_1,
        timestamp=datetime(2024, 1, 1, hour, tzinfo=UTC), open=price, high=price + 1,
        low=price - 1, close=price, volume=1,
    )


@pytest.fixture
def repository(tmp_path: Path) -> DataRepository:
    repo = DataRepository(tmp_path)
    btc_prices = [100, 101, 102, 103, 104, 105]
    eth_prices = [100, 99, 98, 97, 96, 95]
    repo.write(Candle, [_candle("BTCUSDT", h, p) for h, p in enumerate(btc_prices)], exchange="binance", symbol="BTCUSDT", timeframe=Timeframe.HOUR_1)
    repo.write(Candle, [_candle("ETHUSDT", h, p) for h, p in enumerate(eth_prices)], exchange="binance", symbol="ETHUSDT", timeframe=Timeframe.HOUR_1)
    return repo


class TwoSymbolStrategy(Strategy):
    def on_market_event(self, context: StrategyContext) -> Sequence[SignalEvent]:
        if context.timestamp.hour == 0:
            return [SignalEvent(timestamp=context.timestamp, symbol=context.symbol, action=SignalAction.ENTER_LONG, quantity=1.0)]
        if context.timestamp.hour == 4:
            return [SignalEvent(timestamp=context.timestamp, symbol=context.symbol, action=SignalAction.EXIT)]
        return []


def test_shared_portfolio_run_and_per_symbol_attribution(repository: DataRepository) -> None:
    config = BacktestConfig(
        exchange="binance", symbols=["BTCUSDT", "ETHUSDT"], timeframe=Timeframe.HOUR_1,
        start=datetime(2024, 1, 1, tzinfo=UTC), end=datetime(2024, 1, 1, 5, tzinfo=UTC),
        initial_cash=10_000, fee_rate=0, slippage_bps=0,
    )
    report = PortfolioBacktestRunner().run(config=config, repository=repository, strategy=TwoSymbolStrategy())

    # BTC rose (101 -> 105 = +4), ETH fell (99 -> 95 = -4): net zero on shared capital.
    assert report.overall.summary.final_equity == pytest.approx(10_000)
    assert len(report.overall.trades) == 2

    assert set(report.per_symbol) == {"BTCUSDT", "ETHUSDT"}

    btc = report.per_symbol["BTCUSDT"]
    assert btc.trade_count == 1
    assert btc.realized_pnl == pytest.approx(4.0)
    assert btc.win_rate == 1.0
    assert btc.profit_factor == float("inf")

    eth = report.per_symbol["ETHUSDT"]
    assert eth.trade_count == 1
    assert eth.realized_pnl == pytest.approx(-4.0)
    assert eth.win_rate == 0.0
    assert eth.profit_factor == 0.0


def test_symbol_with_no_trades_reports_none_stats(repository: DataRepository) -> None:
    class OnlyBtcStrategy(Strategy):
        def on_market_event(self, context: StrategyContext) -> Sequence[SignalEvent]:
            if context.symbol == "BTCUSDT" and context.timestamp.hour == 0:
                return [SignalEvent(timestamp=context.timestamp, symbol=context.symbol, action=SignalAction.ENTER_LONG, quantity=1.0)]
            if context.symbol == "BTCUSDT" and context.timestamp.hour == 4:
                return [SignalEvent(timestamp=context.timestamp, symbol=context.symbol, action=SignalAction.EXIT)]
            return []

    config = BacktestConfig(
        exchange="binance", symbols=["BTCUSDT", "ETHUSDT"], timeframe=Timeframe.HOUR_1,
        start=datetime(2024, 1, 1, tzinfo=UTC), end=datetime(2024, 1, 1, 5, tzinfo=UTC),
        initial_cash=10_000, fee_rate=0, slippage_bps=0,
    )
    report = PortfolioBacktestRunner().run(config=config, repository=repository, strategy=OnlyBtcStrategy())

    eth = report.per_symbol["ETHUSDT"]
    assert eth.trade_count == 0
    assert eth.realized_pnl == 0.0
    assert eth.win_rate is None
    assert eth.profit_factor is None
