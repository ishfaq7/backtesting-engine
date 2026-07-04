"""Canonical, provider-agnostic market data models.

Every data provider adapter (CoinGlass today, others later) must translate
its own response shape into these models before anything downstream (cache,
sync service, and eventually the Strategy/Backtesting Engines) ever sees the
data. Nothing outside ``btengine.data.providers.*`` should know a provider
other than "the canonical schema" exists.

All models are immutable (``frozen=True``) since a validated historical
record should never be mutated in place once it enters the cache.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

_TIMEFRAME_UNIT_TO_TIMEDELTA_KWARG = {"m": "minutes", "h": "hours", "d": "days", "w": "weeks"}


class Timeframe(str, Enum):
    """Supported bar/aggregation intervals, independent of any provider's naming."""

    MIN_1 = "1m"
    MIN_5 = "5m"
    MIN_15 = "15m"
    MIN_30 = "30m"
    HOUR_1 = "1h"
    HOUR_4 = "4h"
    HOUR_12 = "12h"
    DAY_1 = "1d"
    WEEK_1 = "1w"

    @property
    def duration(self) -> timedelta:
        """The wall-clock length of one bar, used for gap detection."""
        amount, unit = int(self.value[:-1]), self.value[-1]
        return timedelta(**{_TIMEFRAME_UNIT_TO_TIMEDELTA_KWARG[unit]: amount})


class CanonicalRecord(BaseModel):
    """Fields shared by every canonical record type."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    exchange: str
    symbol: str
    timestamp: datetime

    @field_validator("exchange", "symbol")
    @classmethod
    def _normalize_identifier(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must not be empty")
        return value.upper()

    @field_validator("timestamp")
    @classmethod
    def _require_timezone_aware_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("timestamp must be timezone-aware")
        return value.astimezone(timezone.utc)


class Candle(CanonicalRecord):
    """A single OHLCV bar for one symbol/timeframe."""

    timeframe: Timeframe
    open: float = Field(ge=0)
    high: float = Field(ge=0)
    low: float = Field(ge=0)
    close: float = Field(ge=0)
    volume: float = Field(ge=0)

    @model_validator(mode="after")
    def _validate_ohlc_consistency(self) -> "Candle":
        highest = max(self.open, self.close, self.low, self.high)
        lowest = min(self.open, self.close, self.high, self.low)
        if self.high != highest:
            raise ValueError(
                f"high ({self.high}) must be the maximum of open/high/low/close"
            )
        if self.low != lowest:
            raise ValueError(
                f"low ({self.low}) must be the minimum of open/high/low/close"
            )
        return self


class FundingRate(CanonicalRecord):
    """A funding rate observation for a perpetual futures contract."""

    funding_rate: float
    predicted_funding_rate: float | None = None


class OpenInterest(CanonicalRecord):
    """Open interest snapshot/bar for a futures contract."""

    open_interest: float = Field(ge=0)
    open_interest_value_usd: float | None = Field(default=None, ge=0)


class Liquidation(CanonicalRecord):
    """Aggregated long/short liquidation volume for one bar interval."""

    long_liquidation_usd: float = Field(ge=0)
    short_liquidation_usd: float = Field(ge=0)


class LongShortRatio(CanonicalRecord):
    """Global account long/short ratio for a symbol."""

    long_account_ratio: float = Field(ge=0, le=1)
    short_account_ratio: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def _ratios_must_sum_to_one(self) -> "LongShortRatio":
        total = self.long_account_ratio + self.short_account_ratio
        if not (0.98 <= total <= 1.02):
            raise ValueError(
                f"long_account_ratio + short_account_ratio must be ~1.0, got {total}"
            )
        return self

    @property
    def long_short_ratio(self) -> float:
        if self.short_account_ratio == 0:
            return float("inf")
        return self.long_account_ratio / self.short_account_ratio
