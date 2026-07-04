from btengine.backtest.errors import BacktestEngineError, ClockError, EngineConfigurationError, UnknownEventError


def test_error_hierarchy() -> None:
    assert issubclass(ClockError, BacktestEngineError)
    assert issubclass(EngineConfigurationError, BacktestEngineError)
    assert issubclass(UnknownEventError, BacktestEngineError)


def test_error_carries_context() -> None:
    error = EngineConfigurationError("bad config", context={"field": "symbols"})
    assert error.message == "bad config"
    assert error.context == {"field": "symbols"}
