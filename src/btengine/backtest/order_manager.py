"""Translates strategy signals into orders, and orders into simulated fills.

This is mechanical translation, not trading logic: it does not decide
*when* to trade (that's the strategy's job) — only *how* an abstract
``ENTER_LONG``/``ENTER_SHORT``/``EXIT`` intent becomes a concrete buy/sell
order, and how that order is filled in simulation. Orders are queued and
executed against the *next* bar's open (never the bar that produced the
signal) — this is what keeps the engine lookahead-free: a signal produced
after seeing bar T can only affect the simulation from bar T+1 onward.
"""

from __future__ import annotations

import logging
from collections import defaultdict

from btengine.backtest.events import FillEvent, OrderEvent, OrderSide, SignalAction, SignalEvent
from btengine.backtest.position_manager import Position, PositionManager
from btengine.data.schema import Candle

logger = logging.getLogger("btengine.backtest.order_manager")


class OrderManager:
    """Validates signals into orders and simulates their execution."""

    def __init__(self, *, known_symbols: set[str], fee_rate: float, slippage_bps: float) -> None:
        if fee_rate < 0:
            raise ValueError("fee_rate must not be negative")
        if slippage_bps < 0:
            raise ValueError("slippage_bps must not be negative")
        self._known_symbols = known_symbols
        self._fee_rate = fee_rate
        self._slippage_bps = slippage_bps
        self._pending_orders: dict[str, list[OrderEvent]] = defaultdict(list)

    def validate_signal(self, signal: SignalEvent, position_manager: PositionManager) -> OrderEvent | None:
        """Convert a signal into an order, or reject it with a logged reason."""
        if signal.symbol not in self._known_symbols:
            logger.warning(
                "signal rejected: unknown symbol", extra={"symbol": signal.symbol, "action": signal.action.value}
            )
            return None

        position = position_manager.get_position(signal.symbol)

        if signal.action in (SignalAction.ENTER_LONG, SignalAction.ENTER_SHORT):
            return self._validate_entry(signal)
        if signal.action == SignalAction.EXIT:
            return self._validate_exit(signal, position)

        logger.warning(
            "signal rejected: unrecognized action", extra={"symbol": signal.symbol, "action": str(signal.action)}
        )
        return None

    def _validate_entry(self, signal: SignalEvent) -> OrderEvent | None:
        if signal.quantity is None or signal.quantity <= 0:
            logger.warning(
                "signal rejected: entry requires a positive quantity",
                extra={"symbol": signal.symbol, "action": signal.action.value, "quantity": signal.quantity},
            )
            return None
        side = OrderSide.BUY if signal.action == SignalAction.ENTER_LONG else OrderSide.SELL
        return OrderEvent(timestamp=signal.timestamp, symbol=signal.symbol, side=side, quantity=signal.quantity)

    def _validate_exit(self, signal: SignalEvent, position: Position | None) -> OrderEvent | None:
        if position is None:
            logger.warning(
                "signal rejected: no open position to exit", extra={"symbol": signal.symbol}
            )
            return None
        side = OrderSide.SELL if position.quantity > 0 else OrderSide.BUY
        return OrderEvent(
            timestamp=signal.timestamp, symbol=signal.symbol, side=side, quantity=abs(position.quantity)
        )

    def queue_pending(self, order: OrderEvent) -> None:
        """Hold ``order`` until the next bar for its symbol arrives."""
        self._pending_orders[order.symbol].append(order)
        logger.info(
            "order queued for next bar",
            extra={"symbol": order.symbol, "side": order.side.value, "quantity": order.quantity},
        )

    def execute_pending_orders(self, *, symbol: str, bar: Candle) -> list[FillEvent]:
        """Fill every order pending for ``symbol`` against ``bar``'s open price."""
        orders = self._pending_orders.pop(symbol, [])
        fills: list[FillEvent] = []
        for order in orders:
            fill_price = self._apply_slippage(bar.open, order.side)
            fee = fill_price * order.quantity * self._fee_rate
            fill = FillEvent(
                timestamp=bar.timestamp,
                symbol=order.symbol,
                side=order.side,
                quantity=order.quantity,
                fill_price=fill_price,
                fee=fee,
            )
            fills.append(fill)
            logger.info(
                "order filled",
                extra={
                    "symbol": fill.symbol,
                    "side": fill.side.value,
                    "quantity": fill.quantity,
                    "fill_price": fill.fill_price,
                    "fee": fill.fee,
                },
            )
        return fills

    @property
    def has_pending_orders(self) -> bool:
        return any(self._pending_orders.values())

    def _apply_slippage(self, price: float, side: OrderSide) -> float:
        adjustment = price * (self._slippage_bps / 10_000)
        return price + adjustment if side == OrderSide.BUY else price - adjustment
