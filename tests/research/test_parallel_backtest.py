from collections.abc import Sequence
from datetime import datetime, timezone
from pathlib import Path

import pytest

from btengine.backtest.configuration_manager import BacktestConfig
from btengine.data.repository import DataRepository
from btengine.data.schema import Candle, Timeframe
from btengine.research.errors import ValidationConfigError
from btengine.research.parallel_backtest import build_multi_coin_jobs, run_multi_coin_backtest
from btengine.strategy.base import Strategy
from btengine.strategy.context import StrategyContext

UTC = timezone.utc


class NoOpStrategy(Strategy):
    def on_market_event(self, context: StrategyContext) -> Sequence:
        return []


def _candle(symbol: str, hour: int) -> Candle:
    return Candle(
        exchange="binance", symbol=symbol, timeframe=Timeframe.HOUR_1,
        timestamp=datetime(2024, 1, 1, hour, tzinfo=UTC), open=100, high=101, low=99, close=100, volume=1,
    )


@pytest.fixture
def repository(tmp_path: Path) -> DataRepository:
    repo = DataRepository(tmp_path)
    for symbol in ("BTCUSDT", "ETHUSDT", "SOLUSDT"):
        repo.write(Candle, [_candle(symbol, h) for h in range(3)], exchange="binance", symbol=symbol, timeframe=Timeframe.HOUR_1)
    return repo


@pytest.fixture
def base_config() -> BacktestConfig:
    return BacktestConfig(
        exchange="binance", symbols=["PLACEHOLDER"], timeframe=Timeframe.HOUR_1,
        start=datetime(2024, 1, 1, tzinfo=UTC), end=datetime(2024, 1, 1, 2, tzinfo=UTC),
        initial_cash=10_000, fee_rate=0, slippage_bps=0,
    )


def test_build_multi_coin_jobs_rejects_empty_symbols(base_config: BacktestConfig, repository: DataRepository) -> None:
    with pytest.raises(ValidationConfigError):
        build_multi_coin_jobs(symbols=[], base_config=base_config, repository=repository, strategy_factory=NoOpStrategy)


def test_build_multi_coin_jobs_creates_one_job_per_symbol(base_config: BacktestConfig, repository: DataRepository) -> None:
    jobs = build_multi_coin_jobs(
        symbols=["BTCUSDT", "ETHUSDT"], base_config=base_config, repository=repository, strategy_factory=NoOpStrategy
    )
    assert [job.name for job in jobs] == ["BTCUSDT", "ETHUSDT"]
    assert jobs[0].config.symbols == ["BTCUSDT"]
    assert jobs[1].config.symbols == ["ETHUSDT"]
    # every other config field is inherited unchanged from base_config
    assert jobs[0].config.initial_cash == base_config.initial_cash
    assert jobs[0].config.timeframe == base_config.timeframe


def test_run_multi_coin_backtest_runs_each_symbol_independently(
    base_config: BacktestConfig, repository: DataRepository
) -> None:
    results = run_multi_coin_backtest(
        symbols=["BTCUSDT", "ETHUSDT", "SOLUSDT"], base_config=base_config,
        repository=repository, strategy_factory=NoOpStrategy,
    )
    assert [r.name for r in results] == ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
    assert all(r.result is not None for r in results)
    # each ran with its own full initial_cash - not shared capital
    assert all(r.result.summary.final_equity == 10_000 for r in results)
