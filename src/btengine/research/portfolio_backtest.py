"""Portfolio backtesting: one shared capital pool across multiple symbols.

The Core Backtesting Engine already supports this mechanically —
:class:`~btengine.backtest.data_feed.HistoricalCandleFeed` merges several
symbols into one chronological stream, and
:class:`~btengine.backtest.portfolio_state.PortfolioState` already sums
unrealized PnL across every open position regardless of symbol — so a
:class:`~btengine.backtest.configuration_manager.BacktestConfig` with
multiple ``symbols`` is *already* a portfolio backtest. This module adds
only what's missing: a per-symbol performance breakdown, computed after
the fact from the engine's own (unmodified) output, so a shared-capital
run can still be attributed back to which symbol drove the result.

Distinct from :mod:`parallel_backtest`, which runs *independent*,
separately-capitalized backtests per symbol — this runs *one* backtest
with *one* shared portfolio.
"""

from __future__ import annotations

from dataclasses import dataclass

from btengine.backtest.configuration_manager import BacktestConfig
from btengine.backtest.data_feed import HistoricalCandleFeed
from btengine.backtest.engine import BacktestEngine, BacktestResult
from btengine.backtest.position_manager import ClosedTrade
from btengine.data.repository import DataRepository
from btengine.strategy.base import Strategy


@dataclass(frozen=True)
class SymbolAttribution:
    """Trade-level performance attribution for one symbol within a shared-
    capital portfolio run.

    Deliberately does not report a per-symbol "return" or "final equity":
    capital is shared across symbols in a portfolio run, so attributing a
    fraction of it to one symbol would be an arbitrary, misleading
    allocation. Only quantities that are legitimately per-symbol are
    reported.
    """

    symbol: str
    trade_count: int
    realized_pnl: float
    win_rate: float | None
    profit_factor: float | None


@dataclass(frozen=True)
class PortfolioBacktestReport:
    overall: BacktestResult
    per_symbol: dict[str, SymbolAttribution]


class PortfolioBacktestRunner:
    """Runs one shared-portfolio backtest and attributes results per symbol."""

    def run(
        self, *, config: BacktestConfig, repository: DataRepository, strategy: Strategy
    ) -> PortfolioBacktestReport:
        feed = HistoricalCandleFeed(
            repository,
            exchange=config.exchange,
            symbols=config.symbols,
            timeframe=config.timeframe,
            start=config.start,
            end=config.end,
        )
        engine = BacktestEngine(config=config, repository=repository, data_feed=feed, strategy=strategy)
        result = engine.run()

        per_symbol = {
            symbol: _attribute(symbol, [trade for trade in result.trades if trade.symbol == symbol])
            for symbol in config.symbols
        }
        return PortfolioBacktestReport(overall=result, per_symbol=per_symbol)


def _attribute(symbol: str, trades: list[ClosedTrade]) -> SymbolAttribution:
    realized_pnl = sum(trade.realized_pnl for trade in trades)
    wins = [trade.realized_pnl for trade in trades if trade.realized_pnl > 0]
    losses = [trade.realized_pnl for trade in trades if trade.realized_pnl < 0]
    win_rate = len(wins) / len(trades) if trades else None
    gross_loss = abs(sum(losses))
    profit_factor = (sum(wins) / gross_loss) if gross_loss > 0 else (float("inf") if wins else None)
    return SymbolAttribution(
        symbol=symbol, trade_count=len(trades), realized_pnl=realized_pnl,
        win_rate=win_rate, profit_factor=profit_factor,
    )
