"""Account-level bookkeeping: cash balance and equity.

Uses a margin-account model appropriate for the crypto futures/perpetuals
domain this platform targets: opening a position does not deduct its
notional value from cash (positions are margined, not fully funded); cash
only moves on realized PnL and fees. Unrealized PnL from open positions is
added on top to get total equity.
"""

from __future__ import annotations

from btengine.backtest.position_manager import PositionManager
from btengine.strategy.context import PortfolioSnapshot, PositionSnapshot


class PortfolioState:
    """Tracks cash and derives equity from the current open positions."""

    def __init__(self, *, initial_cash: float, position_manager: PositionManager) -> None:
        self._initial_cash = initial_cash
        self._cash = initial_cash
        self._position_manager = position_manager

    @property
    def initial_cash(self) -> float:
        return self._initial_cash

    @property
    def cash(self) -> float:
        return self._cash

    @property
    def unrealized_pnl(self) -> float:
        return sum(position.unrealized_pnl for position in self._position_manager.positions.values())

    @property
    def equity(self) -> float:
        return self._cash + self.unrealized_pnl

    def apply_realized_pnl(self, amount: float) -> None:
        self._cash += amount

    def apply_fee(self, fee: float) -> None:
        self._cash -= fee

    def snapshot(self) -> PortfolioSnapshot:
        """A read-only view suitable for handing to a strategy plugin."""
        positions = {
            symbol: PositionSnapshot(
                symbol=position.symbol,
                quantity=position.quantity,
                avg_entry_price=position.avg_entry_price,
                unrealized_pnl=position.unrealized_pnl,
            )
            for symbol, position in self._position_manager.positions.items()
        }
        return PortfolioSnapshot(cash=self._cash, equity=self.equity, positions=positions)
