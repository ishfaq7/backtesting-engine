from datetime import datetime, timezone

from btengine.backtest.events import FillEvent, OrderEvent, OrderSide
from btengine.integrations.live_trading import LiveExecutionHandler, LiveMarketDataFeed

UTC = timezone.utc


class ConformingFeed:
    def iter_live(self):
        yield from ()


class ConformingExecutionHandler:
    def submit_order(self, order: OrderEvent) -> FillEvent:
        return FillEvent(
            timestamp=order.timestamp, symbol=order.symbol, side=order.side,
            quantity=order.quantity, fill_price=100.0, fee=0.0,
        )


class NonConforming:
    pass


def test_conforming_feed_satisfies_protocol() -> None:
    assert isinstance(ConformingFeed(), LiveMarketDataFeed)


def test_conforming_execution_handler_satisfies_protocol() -> None:
    assert isinstance(ConformingExecutionHandler(), LiveExecutionHandler)


def test_nonconforming_class_satisfies_neither_protocol() -> None:
    instance = NonConforming()
    assert not isinstance(instance, LiveMarketDataFeed)
    assert not isinstance(instance, LiveExecutionHandler)


def test_conforming_execution_handler_behaves_as_expected() -> None:
    handler: LiveExecutionHandler = ConformingExecutionHandler()
    order = OrderEvent(timestamp=datetime(2024, 1, 1, tzinfo=UTC), symbol="BTCUSDT", side=OrderSide.BUY, quantity=1.0)
    fill = handler.submit_order(order)
    assert fill.symbol == "BTCUSDT"
    assert fill.fill_price == 100.0
