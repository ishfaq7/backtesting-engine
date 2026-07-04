"""Derives summary performance statistics from the equity curve and trade log.

Purely descriptive: it measures what happened after the fact. It has no
influence on the simulation and makes no trading decisions.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from btengine.backtest.position_manager import ClosedTrade


@dataclass(frozen=True)
class PerformanceSummary:
    initial_cash: float
    final_equity: float
    total_return: float
    max_drawdown: float
    num_trades: int
    win_rate: float | None
    profit_factor: float | None


class PerformanceTracker:
    """Records the equity curve and computes summary statistics from it."""

    def __init__(self, *, initial_cash: float) -> None:
        self._initial_cash = initial_cash
        self._equity_curve: list[tuple[datetime, float]] = []

    def record_snapshot(self, timestamp: datetime, equity: float) -> None:
        self._equity_curve.append((timestamp, equity))

    @property
    def equity_curve(self) -> list[tuple[datetime, float]]:
        return list(self._equity_curve)

    def max_drawdown(self) -> float:
        peak = float("-inf")
        max_dd = 0.0
        for _, equity in self._equity_curve:
            peak = max(peak, equity)
            if peak > 0:
                drawdown = (peak - equity) / peak
                max_dd = max(max_dd, drawdown)
        return max_dd

    def summary(self, trades: Sequence[ClosedTrade]) -> PerformanceSummary:
        final_equity = self._equity_curve[-1][1] if self._equity_curve else self._initial_cash
        total_return = (
            (final_equity - self._initial_cash) / self._initial_cash if self._initial_cash else 0.0
        )

        wins = [t.realized_pnl for t in trades if t.realized_pnl > 0]
        losses = [t.realized_pnl for t in trades if t.realized_pnl < 0]
        win_rate = len(wins) / len(trades) if trades else None
        gross_loss = abs(sum(losses))
        profit_factor = (sum(wins) / gross_loss) if gross_loss > 0 else (float("inf") if wins else None)

        return PerformanceSummary(
            initial_cash=self._initial_cash,
            final_equity=final_equity,
            total_return=total_return,
            max_drawdown=self.max_drawdown(),
            num_trades=len(trades),
            win_rate=win_rate,
            profit_factor=profit_factor,
        )
