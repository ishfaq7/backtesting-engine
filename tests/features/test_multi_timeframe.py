from datetime import datetime, timezone
from pathlib import Path

import pytest

from btengine.data.repository import DataRepository
from btengine.data.schema import Candle, Timeframe
from btengine.features.multi_timeframe import MultiTimeframeView, build_multi_timeframe_view
from btengine.strategy.context import HistoryView

UTC = timezone.utc


class FakeClock:
    def __init__(self, now: datetime) -> None:
        self.now = now


def _candle(timeframe: Timeframe, hour: int) -> Candle:
    return Candle(
        exchange="binance", symbol="BTCUSDT", timeframe=timeframe,
        timestamp=datetime(2024, 1, 1, hour, tzinfo=UTC), open=100, high=101, low=99, close=100, volume=1,
    )


@pytest.fixture
def repository(tmp_path: Path) -> DataRepository:
    repo = DataRepository(tmp_path)
    repo.write(Candle, [_candle(Timeframe.HOUR_1, h) for h in range(5)], exchange="binance", symbol="BTCUSDT", timeframe=Timeframe.HOUR_1)
    repo.write(Candle, [_candle(Timeframe.HOUR_4, h) for h in (0, 4)], exchange="binance", symbol="BTCUSDT", timeframe=Timeframe.HOUR_4)
    return repo


def test_rejects_empty_views() -> None:
    with pytest.raises(ValueError):
        MultiTimeframeView({})


def test_get_candles_dispatches_to_the_right_timeframe(repository: DataRepository) -> None:
    clock = FakeClock(datetime(2024, 1, 1, 4, tzinfo=UTC))
    view = build_multi_timeframe_view(
        repository, clock, exchange="binance", symbol="BTCUSDT",
        timeframes=[Timeframe.HOUR_1, Timeframe.HOUR_4],
    )
    assert view.timeframes == frozenset({Timeframe.HOUR_1, Timeframe.HOUR_4})

    hourly = view.get_candles(Timeframe.HOUR_1, lookback_periods=3)
    assert [c.timestamp.hour for c in hourly] == [1, 2, 3, 4]

    four_hour = view.get_candles(Timeframe.HOUR_4, lookback_periods=1)
    assert [c.timestamp.hour for c in four_hour] == [0, 4]


def test_get_candles_raises_for_unconfigured_timeframe(repository: DataRepository) -> None:
    clock = FakeClock(datetime(2024, 1, 1, 4, tzinfo=UTC))
    view = build_multi_timeframe_view(
        repository, clock, exchange="binance", symbol="BTCUSDT", timeframes=[Timeframe.HOUR_1]
    )
    with pytest.raises(KeyError):
        view.get_candles(Timeframe.DAY_1, lookback_periods=1)


def test_respects_lookahead_prevention_per_timeframe(repository: DataRepository) -> None:
    clock = FakeClock(datetime(2024, 1, 1, 2, tzinfo=UTC))
    view = build_multi_timeframe_view(
        repository, clock, exchange="binance", symbol="BTCUSDT",
        timeframes=[Timeframe.HOUR_1, Timeframe.HOUR_4],
    )
    hourly = view.get_candles(Timeframe.HOUR_1, start=datetime(2024, 1, 1, 0, tzinfo=UTC))
    assert all(c.timestamp <= clock.now for c in hourly)
    four_hour = view.get_candles(Timeframe.HOUR_4, start=datetime(2024, 1, 1, 0, tzinfo=UTC))
    assert all(c.timestamp <= clock.now for c in four_hour)


def test_can_be_constructed_directly_from_history_views(repository: DataRepository) -> None:
    clock = FakeClock(datetime(2024, 1, 1, 4, tzinfo=UTC))
    hourly_view = HistoryView(repository, clock, exchange="binance", symbol="BTCUSDT", timeframe=Timeframe.HOUR_1)
    view = MultiTimeframeView({Timeframe.HOUR_1: hourly_view})
    assert view.timeframes == frozenset({Timeframe.HOUR_1})
