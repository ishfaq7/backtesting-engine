from collections.abc import Sequence
from datetime import datetime, timezone
from pathlib import Path

import pytest

from btengine.backtest.configuration_manager import BacktestConfig
from btengine.data.repository import DataRepository
from btengine.data.schema import Candle, Timeframe
from btengine.research.batch_backtest import BacktestJob, BatchBacktestRunner
from btengine.research.errors import ValidationConfigError
from btengine.strategy.base import Strategy
from btengine.strategy.context import StrategyContext

UTC = timezone.utc


class NoOpStrategy(Strategy):
    def on_market_event(self, context: StrategyContext) -> Sequence:
        return []


class RaisingStrategy(Strategy):
    def on_market_event(self, context: StrategyContext) -> Sequence:
        raise RuntimeError("boom")


def _candle(symbol: str, hour: int) -> Candle:
    return Candle(
        exchange="binance", symbol=symbol, timeframe=Timeframe.HOUR_1,
        timestamp=datetime(2024, 1, 1, hour, tzinfo=UTC), open=100, high=101, low=99, close=100, volume=1,
    )


@pytest.fixture
def repository(tmp_path: Path) -> DataRepository:
    repo = DataRepository(tmp_path)
    for symbol in ("BTCUSDT", "ETHUSDT"):
        repo.write(Candle, [_candle(symbol, h) for h in range(3)], exchange="binance", symbol=symbol, timeframe=Timeframe.HOUR_1)
    return repo


def _config(symbol: str) -> BacktestConfig:
    return BacktestConfig(
        exchange="binance", symbols=[symbol], timeframe=Timeframe.HOUR_1,
        start=datetime(2024, 1, 1, tzinfo=UTC), end=datetime(2024, 1, 1, 2, tzinfo=UTC),
        initial_cash=10_000, fee_rate=0, slippage_bps=0,
    )


def test_constructor_rejects_nonpositive_max_workers() -> None:
    with pytest.raises(ValidationConfigError):
        BatchBacktestRunner(max_workers=0)


def test_run_sequential_executes_all_jobs(repository: DataRepository) -> None:
    jobs = [
        BacktestJob(name="btc", config=_config("BTCUSDT"), repository=repository, strategy_factory=NoOpStrategy),
        BacktestJob(name="eth", config=_config("ETHUSDT"), repository=repository, strategy_factory=NoOpStrategy),
    ]
    results = BatchBacktestRunner(max_workers=1).run(jobs)
    assert [r.name for r in results] == ["btc", "eth"]
    assert all(r.result is not None and r.error is None for r in results)
    assert all(r.result.summary.final_equity == 10_000 for r in results)


def test_run_parallel_executes_all_jobs_and_preserves_order(repository: DataRepository) -> None:
    jobs = [
        BacktestJob(name="btc", config=_config("BTCUSDT"), repository=repository, strategy_factory=NoOpStrategy),
        BacktestJob(name="eth", config=_config("ETHUSDT"), repository=repository, strategy_factory=NoOpStrategy),
    ]
    results = BatchBacktestRunner(max_workers=2).run(jobs)
    assert [r.name for r in results] == ["btc", "eth"]
    assert all(r.result is not None for r in results)


def test_one_failing_job_does_not_prevent_others_from_completing(repository: DataRepository) -> None:
    jobs = [
        BacktestJob(name="ok", config=_config("BTCUSDT"), repository=repository, strategy_factory=NoOpStrategy),
        BacktestJob(name="broken", config=_config("ETHUSDT"), repository=repository, strategy_factory=RaisingStrategy),
    ]
    results = BatchBacktestRunner(max_workers=1).run(jobs)
    ok, broken = results
    assert ok.result is not None
    assert ok.error is None
    assert broken.result is None
    assert broken.error is not None
    assert "boom" in broken.error


def test_each_job_gets_a_fresh_strategy_instance(repository: DataRepository) -> None:
    created = []

    class TrackingStrategy(Strategy):
        def __init__(self) -> None:
            created.append(self)

        def on_market_event(self, context: StrategyContext) -> Sequence:
            return []

    jobs = [
        BacktestJob(name="btc", config=_config("BTCUSDT"), repository=repository, strategy_factory=TrackingStrategy),
        BacktestJob(name="eth", config=_config("ETHUSDT"), repository=repository, strategy_factory=TrackingStrategy),
    ]
    BatchBacktestRunner(max_workers=1).run(jobs)
    assert len(created) == 2
    assert created[0] is not created[1]
