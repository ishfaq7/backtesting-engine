"""Monte Carlo validation via trade-sequence resampling.

A standard, non-proprietary technique for gauging how much of a completed
backtest's result is order-dependent luck versus robust edge: the realized
per-trade PnLs are resampled with replacement many times, each resample is
replayed as an alternative equity curve, and the resulting distribution of
outcomes is summarized. This operates only on already-recorded
:class:`~btengine.backtest.position_manager.ClosedTrade` PnL values — it
never re-runs the strategy, queries market data, or makes any trading
decision, so it has no dependency on (and does not need to import) the
Core Backtesting Engine.
"""

from __future__ import annotations

import math
import random
from collections.abc import Sequence
from dataclasses import dataclass

from btengine.backtest.position_manager import ClosedTrade
from btengine.research.errors import ValidationConfigError

_DEFAULT_PERCENTILES = (5, 25, 50, 75, 95)


@dataclass(frozen=True)
class MonteCarloResult:
    simulations: int
    final_equity_percentiles: dict[int, float]
    max_drawdown_percentiles: dict[int, float]
    probability_of_loss: float


class MonteCarloValidator:
    """Bootstraps a distribution of alternative equity outcomes from a
    completed backtest's trade PnLs.
    """

    def __init__(
        self,
        *,
        simulations: int = 1000,
        percentiles: Sequence[int] = _DEFAULT_PERCENTILES,
        random_seed: int | None = None,
    ) -> None:
        if simulations <= 0:
            raise ValidationConfigError("simulations must be positive")
        if not percentiles:
            raise ValidationConfigError("percentiles must not be empty")
        if any(not (0 <= p <= 100) for p in percentiles):
            raise ValidationConfigError("percentiles must each be in [0, 100]")
        self._simulations = simulations
        self._percentiles = tuple(sorted(percentiles))
        self._random = random.Random(random_seed)

    def validate(self, trades: Sequence[ClosedTrade], *, initial_cash: float) -> MonteCarloResult:
        if initial_cash <= 0:
            raise ValidationConfigError("initial_cash must be positive")

        pnls = [trade.realized_pnl for trade in trades]
        if not pnls:
            return MonteCarloResult(
                simulations=self._simulations,
                final_equity_percentiles={p: initial_cash for p in self._percentiles},
                max_drawdown_percentiles={p: 0.0 for p in self._percentiles},
                probability_of_loss=0.0,
            )

        final_equities: list[float] = []
        max_drawdowns: list[float] = []
        losing_runs = 0

        for _ in range(self._simulations):
            resampled = self._random.choices(pnls, k=len(pnls))
            equity = initial_cash
            peak = initial_cash
            max_drawdown = 0.0
            for pnl in resampled:
                equity += pnl
                peak = max(peak, equity)
                if peak > 0:
                    max_drawdown = max(max_drawdown, (peak - equity) / peak)
            final_equities.append(equity)
            max_drawdowns.append(max_drawdown)
            if equity < initial_cash:
                losing_runs += 1

        return MonteCarloResult(
            simulations=self._simulations,
            final_equity_percentiles=_percentiles_of(final_equities, self._percentiles),
            max_drawdown_percentiles=_percentiles_of(max_drawdowns, self._percentiles),
            probability_of_loss=losing_runs / self._simulations,
        )


def _percentiles_of(values: list[float], percentiles: Sequence[int]) -> dict[int, float]:
    ordered = sorted(values)
    return {p: _percentile(ordered, p) for p in percentiles}


def _percentile(sorted_values: list[float], pct: int) -> float:
    if len(sorted_values) == 1:
        return sorted_values[0]
    rank = (pct / 100) * (len(sorted_values) - 1)
    lower = math.floor(rank)
    upper = math.ceil(rank)
    if lower == upper:
        return sorted_values[int(rank)]
    lower_weight = upper - rank
    upper_weight = rank - lower
    return sorted_values[lower] * lower_weight + sorted_values[upper] * upper_weight
