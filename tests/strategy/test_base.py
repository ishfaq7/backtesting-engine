import pytest

from btengine.strategy.base import Strategy


def test_strategy_cannot_be_instantiated_directly() -> None:
    with pytest.raises(TypeError):
        Strategy()  # type: ignore[abstract]


def test_concrete_strategy_must_implement_on_market_event() -> None:
    class IncompleteStrategy(Strategy):
        pass

    with pytest.raises(TypeError):
        IncompleteStrategy()  # type: ignore[abstract]


def test_concrete_strategy_can_be_instantiated_when_implemented() -> None:
    class MinimalStrategy(Strategy):
        def on_market_event(self, context):  # type: ignore[override]
            return []

    strategy = MinimalStrategy()
    assert strategy.on_market_event(None) == []  # type: ignore[arg-type]
