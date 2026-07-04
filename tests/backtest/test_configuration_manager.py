from datetime import datetime, timezone

import pytest

from btengine.backtest.configuration_manager import BacktestConfig, ConfigurationManager
from btengine.backtest.errors import EngineConfigurationError
from btengine.data.schema import Timeframe

UTC = timezone.utc


def _valid_kwargs() -> dict:
    return {
        "exchange": "binance",
        "symbols": ["btcusdt"],
        "timeframe": Timeframe.HOUR_1,
        "start": datetime(2024, 1, 1, tzinfo=UTC),
        "end": datetime(2024, 1, 2, tzinfo=UTC),
        "initial_cash": 10_000,
    }


def test_valid_config_normalizes_exchange_and_symbols() -> None:
    manager = ConfigurationManager.from_mapping(_valid_kwargs())
    assert manager.config.exchange == "BINANCE"
    assert manager.config.symbols == ["BTCUSDT"]


def test_defaults_are_applied() -> None:
    manager = ConfigurationManager.from_mapping(_valid_kwargs())
    assert manager.config.fee_rate == 0.0004
    assert manager.config.slippage_bps == 1.0


def test_end_before_start_is_rejected() -> None:
    kwargs = _valid_kwargs()
    kwargs["end"] = datetime(2023, 1, 1, tzinfo=UTC)
    with pytest.raises(EngineConfigurationError):
        ConfigurationManager.from_mapping(kwargs)


def test_naive_datetimes_are_rejected() -> None:
    kwargs = _valid_kwargs()
    kwargs["start"] = datetime(2024, 1, 1)
    with pytest.raises(EngineConfigurationError):
        ConfigurationManager.from_mapping(kwargs)


def test_empty_symbols_is_rejected() -> None:
    kwargs = _valid_kwargs()
    kwargs["symbols"] = []
    with pytest.raises(EngineConfigurationError):
        ConfigurationManager.from_mapping(kwargs)


def test_blank_exchange_is_rejected() -> None:
    kwargs = _valid_kwargs()
    kwargs["exchange"] = "   "
    with pytest.raises(EngineConfigurationError):
        ConfigurationManager.from_mapping(kwargs)


def test_blank_symbol_string_is_rejected() -> None:
    kwargs = _valid_kwargs()
    kwargs["symbols"] = ["BTCUSDT", "   "]
    with pytest.raises(EngineConfigurationError):
        ConfigurationManager.from_mapping(kwargs)


def test_duplicate_symbols_are_rejected() -> None:
    kwargs = _valid_kwargs()
    kwargs["symbols"] = ["BTCUSDT", "btcusdt"]
    with pytest.raises(EngineConfigurationError):
        ConfigurationManager.from_mapping(kwargs)


def test_nonpositive_initial_cash_is_rejected() -> None:
    kwargs = _valid_kwargs()
    kwargs["initial_cash"] = 0
    with pytest.raises(EngineConfigurationError):
        ConfigurationManager.from_mapping(kwargs)


def test_negative_fee_rate_is_rejected() -> None:
    kwargs = _valid_kwargs()
    kwargs["fee_rate"] = -0.01
    with pytest.raises(EngineConfigurationError):
        ConfigurationManager.from_mapping(kwargs)


def test_config_is_frozen() -> None:
    manager = ConfigurationManager.from_mapping(_valid_kwargs())
    with pytest.raises(Exception):
        manager.config.initial_cash = 1  # type: ignore[misc]


def test_unknown_field_is_rejected() -> None:
    kwargs = _valid_kwargs()
    kwargs["strategy_secret_sauce"] = "nope"
    with pytest.raises(EngineConfigurationError):
        ConfigurationManager.from_mapping(kwargs)
