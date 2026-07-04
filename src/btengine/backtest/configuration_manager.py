"""Loads and validates the parameters for a single backtest run.

Deliberately knows nothing about any strategy's parameters — those belong
to the strategy plugin's own config (see ``docs/STRATEGY_AND_DATA_LAYER.md``).
This only covers what the *engine* needs to run: which market(s), what
range, starting capital, and the simulated cost model.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from btengine.backtest.errors import EngineConfigurationError
from btengine.data.schema import Timeframe


class BacktestConfig(BaseModel):
    """Validated configuration for one backtest run."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    exchange: str
    symbols: list[str] = Field(min_length=1)
    timeframe: Timeframe
    start: datetime
    end: datetime
    initial_cash: float = Field(gt=0)
    fee_rate: float = Field(ge=0, default=0.0004)
    slippage_bps: float = Field(ge=0, default=1.0)

    @field_validator("exchange")
    @classmethod
    def _normalize_exchange(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("exchange must not be empty")
        return value.upper()

    @field_validator("symbols")
    @classmethod
    def _normalize_symbols(cls, value: list[str]) -> list[str]:
        normalized = [symbol.strip().upper() for symbol in value]
        if any(not symbol for symbol in normalized):
            raise ValueError("symbols must not contain empty strings")
        if len(set(normalized)) != len(normalized):
            raise ValueError("symbols must not contain duplicates")
        return normalized

    @field_validator("start", "end")
    @classmethod
    def _require_timezone_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("start/end must be timezone-aware")
        return value

    @model_validator(mode="after")
    def _end_after_start(self) -> "BacktestConfig":
        if self.end <= self.start:
            raise ValueError("end must be after start")
        return self


class ConfigurationManager:
    """Loads a :class:`BacktestConfig`, converting validation failures into
    a structured :class:`~btengine.backtest.errors.EngineConfigurationError`.
    """

    def __init__(self, config: BacktestConfig) -> None:
        self._config = config

    @property
    def config(self) -> BacktestConfig:
        return self._config

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> "ConfigurationManager":
        try:
            return cls(BacktestConfig(**data))
        except ValidationError as exc:
            raise EngineConfigurationError(
                "Invalid backtest configuration", context={"errors": exc.errors()}
            ) from exc
