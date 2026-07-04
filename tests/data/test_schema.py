from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from btengine.data.schema import Candle, FundingRate, LongShortRatio, Timeframe

UTC_NOW = datetime(2024, 1, 1, tzinfo=timezone.utc)


def test_candle_accepts_consistent_ohlc() -> None:
    candle = Candle(
        exchange="binance",
        symbol="btcusdt",
        timeframe=Timeframe.HOUR_1,
        timestamp=UTC_NOW,
        open=100,
        high=110,
        low=95,
        close=105,
        volume=10,
    )
    assert candle.exchange == "BINANCE"
    assert candle.symbol == "BTCUSDT"


@pytest.mark.parametrize(
    "open_, high, low, close",
    [
        (100, 90, 80, 95),  # high below open
        (100, 105, 101, 95),  # low above close
    ],
)
def test_candle_rejects_inconsistent_ohlc(open_: float, high: float, low: float, close: float) -> None:
    with pytest.raises(ValidationError):
        Candle(
            exchange="binance",
            symbol="btcusdt",
            timeframe=Timeframe.HOUR_1,
            timestamp=UTC_NOW,
            open=open_,
            high=high,
            low=low,
            close=close,
            volume=1,
        )


def test_timestamp_must_be_timezone_aware() -> None:
    with pytest.raises(ValidationError):
        FundingRate(
            exchange="binance",
            symbol="btcusdt",
            timestamp=datetime(2024, 1, 1),  # naive
            funding_rate=0.0001,
        )


def test_exchange_and_symbol_must_not_be_blank() -> None:
    with pytest.raises(ValidationError):
        FundingRate(exchange="  ", symbol="btcusdt", timestamp=UTC_NOW, funding_rate=0.0001)


def test_long_short_ratio_must_sum_to_one() -> None:
    with pytest.raises(ValidationError):
        LongShortRatio(
            exchange="binance", symbol="btcusdt", timestamp=UTC_NOW,
            long_account_ratio=0.7, short_account_ratio=0.7,
        )


def test_long_short_ratio_property() -> None:
    ratio = LongShortRatio(
        exchange="binance", symbol="btcusdt", timestamp=UTC_NOW,
        long_account_ratio=0.6, short_account_ratio=0.4,
    )
    assert ratio.long_short_ratio == pytest.approx(1.5)


def test_long_short_ratio_property_handles_zero_short_ratio() -> None:
    ratio = LongShortRatio(
        exchange="binance", symbol="btcusdt", timestamp=UTC_NOW,
        long_account_ratio=1.0, short_account_ratio=0.0,
    )
    assert ratio.long_short_ratio == float("inf")


@pytest.mark.parametrize(
    "timeframe, expected",
    [
        (Timeframe.MIN_1, timedelta(minutes=1)),
        (Timeframe.MIN_5, timedelta(minutes=5)),
        (Timeframe.MIN_15, timedelta(minutes=15)),
        (Timeframe.MIN_30, timedelta(minutes=30)),
        (Timeframe.HOUR_1, timedelta(hours=1)),
        (Timeframe.HOUR_4, timedelta(hours=4)),
        (Timeframe.HOUR_12, timedelta(hours=12)),
        (Timeframe.DAY_1, timedelta(days=1)),
        (Timeframe.WEEK_1, timedelta(weeks=1)),
    ],
)
def test_timeframe_duration(timeframe: Timeframe, expected: timedelta) -> None:
    assert timeframe.duration == expected


def test_models_are_frozen() -> None:
    candle = Candle(
        exchange="binance", symbol="btcusdt", timeframe=Timeframe.HOUR_1, timestamp=UTC_NOW,
        open=1, high=2, low=1, close=1.5, volume=1,
    )
    with pytest.raises(ValidationError):
        candle.close = 999  # type: ignore[misc]
