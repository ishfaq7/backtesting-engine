"""The Core Backtesting Engine: composition root and event dispatch loop.

For every candle, in strict chronological order:

1. Advance the simulation clock to the candle's timestamp.
2. Fill any orders left pending from the previous bar, against *this*
   bar's open (never the bar that produced the signal — see
   ``docs/`` / module docstrings on lookahead prevention).
3. Mark open positions to market using this bar's close and record an
   equity snapshot.
4. Build a :class:`~btengine.strategy.context.StrategyContext` bounded to
   "now" and call the injected strategy's ``on_market_event``.
5. Push every returned signal through the event loop, where it is
   validated into an order and queued for the *next* bar.

The engine depends only on the :class:`~btengine.strategy.base.Strategy`
abstract interface — it never imports, inspects, or has any knowledge of a
concrete strategy implementation.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime

from btengine.backtest.configuration_manager import BacktestConfig
from btengine.backtest.data_feed import HistoricalCandleFeed
from btengine.backtest.errors import UnknownEventError
from btengine.backtest.event_loop import EventLoop
from btengine.backtest.events import Event, FillEvent, MarketEvent, OrderEvent, SignalEvent
from btengine.backtest.order_manager import OrderManager
from btengine.backtest.performance_tracker import PerformanceSummary, PerformanceTracker
from btengine.backtest.portfolio_state import PortfolioState
from btengine.backtest.position_manager import ClosedTrade, PositionManager
from btengine.backtest.simulation_clock import SimulationClock
from btengine.backtest.trade_recorder import TradeRecorder
from btengine.data.repository import DataRepository
from btengine.strategy.base import Strategy
from btengine.strategy.context import HistoryView, StrategyContext

logger = logging.getLogger("btengine.backtest.engine")


@dataclass(frozen=True)
class BacktestResult:
    """Everything produced by one backtest run."""

    trades: list[ClosedTrade]
    equity_curve: list[tuple[datetime, float]]
    summary: PerformanceSummary


class BacktestEngine:
    """Orchestrates a single backtest run over an injected strategy."""

    def __init__(
        self,
        *,
        config: BacktestConfig,
        repository: DataRepository,
        data_feed: HistoricalCandleFeed,
        strategy: Strategy,
    ) -> None:
        self._config = config
        self._repository = repository
        self._data_feed = data_feed
        self._strategy = strategy

        self._clock = SimulationClock(config.start)
        self._event_loop = EventLoop()
        self._position_manager = PositionManager()
        self._portfolio_state = PortfolioState(
            initial_cash=config.initial_cash, position_manager=self._position_manager
        )
        self._order_manager = OrderManager(
            known_symbols=set(config.symbols), fee_rate=config.fee_rate, slippage_bps=config.slippage_bps
        )
        self._trade_recorder = TradeRecorder()
        self._performance_tracker = PerformanceTracker(initial_cash=config.initial_cash)

    def run(self) -> BacktestResult:
        candle_count = 0
        for candle in self._data_feed.iter_chronological():
            self._clock.advance_to(candle.timestamp)
            self._event_loop.push(MarketEvent.from_candle(candle))
            self._drain_event_loop()
            candle_count += 1

        logger.info(
            "backtest run complete",
            extra={
                "candles_processed": candle_count,
                "trades": len(self._trade_recorder),
                "final_equity": self._portfolio_state.equity,
            },
        )
        if self._order_manager.has_pending_orders:
            logger.warning("backtest ended with unfilled pending orders (no next bar to fill them against)")

        return BacktestResult(
            trades=self._trade_recorder.trades,
            equity_curve=self._performance_tracker.equity_curve,
            summary=self._performance_tracker.summary(self._trade_recorder.trades),
        )

    def _drain_event_loop(self) -> None:
        event = self._event_loop.pop()
        while event is not None:
            self._dispatch(event)
            event = self._event_loop.pop()

    def _dispatch(self, event: Event) -> None:
        # FillEvent is intentionally not dispatched here: fills must be applied
        # before the strategy context is built for this same tick, so
        # _handle_market_event applies them synchronously via _apply_fill()
        # rather than round-tripping through the queue.
        if isinstance(event, MarketEvent):
            self._handle_market_event(event)
        elif isinstance(event, SignalEvent):
            self._handle_signal_event(event)
        elif isinstance(event, OrderEvent):
            self._handle_order_event(event)
        else:
            raise UnknownEventError(f"Unknown event type: {type(event)!r}")

    def _handle_market_event(self, event: MarketEvent) -> None:
        for fill in self._order_manager.execute_pending_orders(symbol=event.symbol, bar=event.candle):
            self._apply_fill(fill)

        self._position_manager.mark_to_market(event.candle)
        self._performance_tracker.record_snapshot(event.timestamp, self._portfolio_state.equity)

        context = self._build_context(event)
        signals = self._strategy.on_market_event(context)
        for signal in signals:
            self._event_loop.push(signal)

    def _handle_signal_event(self, event: SignalEvent) -> None:
        order = self._order_manager.validate_signal(event, self._position_manager)
        if order is not None:
            self._event_loop.push(order)

    def _handle_order_event(self, event: OrderEvent) -> None:
        self._order_manager.queue_pending(event)

    def _apply_fill(self, fill: FillEvent) -> None:
        realized_pnl, closed_trade = self._position_manager.apply_fill(fill)
        self._portfolio_state.apply_realized_pnl(realized_pnl)
        self._portfolio_state.apply_fee(fill.fee)
        if closed_trade is not None:
            self._trade_recorder.record(closed_trade)

    def _build_context(self, event: MarketEvent) -> StrategyContext:
        history = HistoryView(
            self._repository,
            self._clock,
            exchange=event.exchange,
            symbol=event.symbol,
            timeframe=self._config.timeframe,
        )
        return StrategyContext(
            timestamp=event.timestamp,
            exchange=event.exchange,
            symbol=event.symbol,
            current_candle=event.candle,
            history=history,
            portfolio=self._portfolio_state.snapshot(),
        )
