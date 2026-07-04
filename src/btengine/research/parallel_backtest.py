"""Multi-coin parallel backtesting: the same strategy, run independently
and concurrently across many symbols (e.g. screening 50 coins).

A thin convenience layer over :mod:`batch_backtest`: it builds one
independent :class:`~btengine.backtest.configuration_manager.BacktestConfig`
per symbol (each with its own isolated capital pool — this is *not* shared-
portfolio backtesting; see :mod:`portfolio_backtest` for that) and runs them
through :class:`~btengine.research.batch_backtest.BatchBacktestRunner`.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

from btengine.backtest.configuration_manager import BacktestConfig
from btengine.data.repository import DataRepository
from btengine.research.batch_backtest import BacktestJob, BatchBacktestResult, BatchBacktestRunner
from btengine.research.errors import ValidationConfigError
from btengine.strategy.base import Strategy


def build_multi_coin_jobs(
    *,
    symbols: Sequence[str],
    base_config: BacktestConfig,
    repository: DataRepository,
    strategy_factory: Callable[[], Strategy],
) -> list[BacktestJob]:
    """Build one single-symbol job per entry in ``symbols``, each derived
    from ``base_config`` with only its ``symbols`` field replaced.
    """
    if not symbols:
        raise ValidationConfigError("symbols must not be empty")
    return [
        BacktestJob(
            name=symbol,
            config=base_config.model_copy(update={"symbols": [symbol]}),
            repository=repository,
            strategy_factory=strategy_factory,
        )
        for symbol in symbols
    ]


def run_multi_coin_backtest(
    *,
    symbols: Sequence[str],
    base_config: BacktestConfig,
    repository: DataRepository,
    strategy_factory: Callable[[], Strategy],
    max_workers: int = 1,
) -> list[BatchBacktestResult]:
    """Run the same strategy independently across every symbol in ``symbols``."""
    jobs = build_multi_coin_jobs(
        symbols=symbols, base_config=base_config, repository=repository, strategy_factory=strategy_factory
    )
    return BatchBacktestRunner(max_workers=max_workers).run(jobs)
