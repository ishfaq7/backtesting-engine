"""Append-only log of completed (closed) trades.

Pure bookkeeping: it does not compute summary statistics (that's
:mod:`~btengine.backtest.performance_tracker`) and it does not decide
whether a trade was "good" — it just remembers what happened.
"""

from __future__ import annotations

import logging

from btengine.backtest.position_manager import ClosedTrade

logger = logging.getLogger("btengine.backtest.trade_recorder")


class TradeRecorder:
    """Records every :class:`ClosedTrade` produced during a backtest run."""

    def __init__(self) -> None:
        self._trades: list[ClosedTrade] = []

    def record(self, trade: ClosedTrade) -> None:
        self._trades.append(trade)
        logger.info(
            "trade recorded",
            extra={
                "symbol": trade.symbol,
                "side": trade.side,
                "quantity": trade.quantity,
                "realized_pnl": trade.realized_pnl,
            },
        )

    @property
    def trades(self) -> list[ClosedTrade]:
        return list(self._trades)

    def __len__(self) -> int:
        return len(self._trades)
