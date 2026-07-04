"""Runs many backtests (different configs, symbols, or strategy instances)
as one batch, sequentially or concurrently.

Pure orchestration over the existing, unmodified
:class:`~btengine.backtest.engine.BacktestEngine` and
:class:`~btengine.backtest.data_feed.HistoricalCandleFeed` — this module
never changes how a single backtest runs, it only runs many of them and
collects the results (including failures, so one bad config doesn't sink
an entire batch).
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

from btengine.backtest.configuration_manager import BacktestConfig
from btengine.backtest.data_feed import HistoricalCandleFeed
from btengine.backtest.engine import BacktestEngine, BacktestResult
from btengine.data.repository import DataRepository
from btengine.research.errors import ValidationConfigError
from btengine.strategy.base import Strategy


@dataclass(frozen=True)
class BacktestJob:
    """One backtest run to perform as part of a batch."""

    name: str
    config: BacktestConfig
    repository: DataRepository
    strategy_factory: Callable[[], Strategy]


@dataclass(frozen=True)
class BatchBacktestResult:
    """The outcome of one :class:`BacktestJob` — exactly one of ``result``
    or ``error`` is set.
    """

    name: str
    result: BacktestResult | None
    error: str | None


class BatchBacktestRunner:
    """Runs a batch of :class:`BacktestJob`\\ s, sequentially or in parallel.

    Each job gets a *fresh* strategy instance from its own
    ``strategy_factory`` — never a shared instance — so running jobs
    concurrently is safe even if a strategy implementation keeps internal
    state.
    """

    def __init__(self, *, max_workers: int = 1) -> None:
        if max_workers <= 0:
            raise ValidationConfigError("max_workers must be positive")
        self._max_workers = max_workers

    def run(self, jobs: Sequence[BacktestJob]) -> list[BatchBacktestResult]:
        if self._max_workers == 1:
            return [_execute(job) for job in jobs]
        with ThreadPoolExecutor(max_workers=self._max_workers) as executor:
            return list(executor.map(_execute, jobs))


def _execute(job: BacktestJob) -> BatchBacktestResult:
    try:
        feed = HistoricalCandleFeed(
            job.repository,
            exchange=job.config.exchange,
            symbols=job.config.symbols,
            timeframe=job.config.timeframe,
            start=job.config.start,
            end=job.config.end,
        )
        engine = BacktestEngine(
            config=job.config, repository=job.repository, data_feed=feed, strategy=job.strategy_factory()
        )
        return BatchBacktestResult(name=job.name, result=engine.run(), error=None)
    except Exception as exc:  # noqa: BLE001 - one bad job must not sink the whole batch
        return BatchBacktestResult(name=job.name, result=None, error=str(exc))
