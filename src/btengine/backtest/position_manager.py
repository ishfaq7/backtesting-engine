"""Per-symbol position accounting.

Uses a standard netted, average-cost-basis model (the same mechanical
bookkeeping any futures broker or backtester needs, independent of what
strategy is running): a fill in the same direction as an open position
extends it at a weighted-average price; a fill in the opposite direction
realizes PnL on the closed portion and, if it overshoots the existing
size, flips the position. None of this decides *when* to trade — it only
answers "what does this fill do to the position," which is pure arithmetic.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime

from btengine.backtest.events import FillEvent, OrderSide
from btengine.data.schema import Candle

logger = logging.getLogger("btengine.backtest.position_manager")


@dataclass
class Position:
    """A single symbol's current position. ``quantity`` is signed."""

    symbol: str
    quantity: float = 0.0
    avg_entry_price: float = 0.0
    unrealized_pnl: float = 0.0

    @property
    def is_open(self) -> bool:
        return self.quantity != 0.0

    @property
    def side(self) -> str:
        if self.quantity > 0:
            return "LONG"
        if self.quantity < 0:
            return "SHORT"
        return "FLAT"


@dataclass(frozen=True)
class ClosedTrade:
    """A record of realized PnL from closing all or part of a position."""

    symbol: str
    side: str  # "LONG" or "SHORT" - the side that was closed
    quantity: float
    entry_price: float
    exit_price: float
    exit_time: datetime
    realized_pnl: float
    fee: float


class PositionManager:
    """Owns every symbol's :class:`Position` and applies fills to them."""

    def __init__(self) -> None:
        self._positions: dict[str, Position] = {}

    @property
    def positions(self) -> dict[str, Position]:
        """All currently-open positions, keyed by symbol."""
        return {symbol: position for symbol, position in self._positions.items() if position.is_open}

    def get_position(self, symbol: str) -> Position | None:
        position = self._positions.get(symbol)
        return position if position is not None and position.is_open else None

    def apply_fill(self, fill: FillEvent) -> tuple[float, ClosedTrade | None]:
        """Apply a fill to the relevant position.

        Returns ``(realized_pnl, closed_trade)``: ``realized_pnl`` is 0.0
        when a fill only opens or extends a position (no trade to record);
        ``closed_trade`` is set whenever the fill closes all or part of an
        existing position.
        """
        position = self._positions.setdefault(fill.symbol, Position(symbol=fill.symbol))
        signed_quantity = fill.quantity if fill.side == OrderSide.BUY else -fill.quantity

        if position.quantity == 0.0 or _same_sign(position.quantity, signed_quantity):
            self._open_or_extend(position, signed_quantity, fill.fill_price)
            logger.info(
                "position opened/extended",
                extra={"symbol": fill.symbol, "quantity": position.quantity, "avg_entry_price": position.avg_entry_price},
            )
            return 0.0, None

        realized_pnl, closed_trade = self._reduce_or_flip(position, signed_quantity, fill)
        logger.info(
            "position reduced/closed/flipped",
            extra={
                "symbol": fill.symbol,
                "realized_pnl": realized_pnl,
                "remaining_quantity": position.quantity,
            },
        )
        return realized_pnl, closed_trade

    def mark_to_market(self, candle: Candle) -> None:
        """Recompute unrealized PnL for ``candle``'s symbol using its close price."""
        position = self._positions.get(candle.symbol)
        if position is None or not position.is_open:
            return
        direction = 1 if position.quantity > 0 else -1
        position.unrealized_pnl = (candle.close - position.avg_entry_price) * abs(position.quantity) * direction

    @staticmethod
    def _open_or_extend(position: Position, signed_quantity: float, fill_price: float) -> None:
        existing_magnitude = abs(position.quantity)
        new_quantity = position.quantity + signed_quantity
        if new_quantity != 0.0:
            position.avg_entry_price = (
                position.avg_entry_price * existing_magnitude + fill_price * abs(signed_quantity)
            ) / abs(new_quantity)
        position.quantity = new_quantity

    @staticmethod
    def _reduce_or_flip(
        position: Position, signed_quantity: float, fill: FillEvent
    ) -> tuple[float, ClosedTrade]:
        direction = 1 if position.quantity > 0 else -1
        existing_magnitude = abs(position.quantity)
        fill_magnitude = abs(signed_quantity)
        closing_magnitude = min(existing_magnitude, fill_magnitude)

        realized_pnl = (fill.fill_price - position.avg_entry_price) * closing_magnitude * direction
        closed_trade = ClosedTrade(
            symbol=fill.symbol,
            side=position.side,
            quantity=closing_magnitude,
            entry_price=position.avg_entry_price,
            exit_price=fill.fill_price,
            exit_time=fill.timestamp,
            realized_pnl=realized_pnl,
            fee=fill.fee,
        )

        remaining_existing = existing_magnitude - closing_magnitude
        remaining_fill = fill_magnitude - closing_magnitude

        if remaining_existing > 0:
            position.quantity = direction * remaining_existing
            # avg_entry_price unchanged: the still-open portion was never repriced
        elif remaining_fill > 0:
            new_direction = 1 if signed_quantity > 0 else -1
            position.quantity = new_direction * remaining_fill
            position.avg_entry_price = fill.fill_price
        else:
            position.quantity = 0.0
            position.avg_entry_price = 0.0

        return realized_pnl, closed_trade


def _same_sign(a: float, b: float) -> bool:
    return (a > 0 and b > 0) or (a < 0 and b < 0)
