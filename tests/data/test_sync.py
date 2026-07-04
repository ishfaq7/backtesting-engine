from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from btengine.data.repository import DataRepository
from btengine.data.schema import Candle, FundingRate, Liquidation, LongShortRatio, OpenInterest, Timeframe
from btengine.data.sync import DataGap, HistoricalDataService, find_gaps

UTC = timezone.utc


# --- find_gaps -----------------------------------------------------------


def test_find_gaps_returns_empty_when_grid_is_full() -> None:
    start = datetime(2024, 1, 1, tzinfo=UTC)
    timestamps = [start + timedelta(hours=h) for h in range(4)]
    gaps = find_gaps(
        timestamps,
        expected_interval=timedelta(hours=1),
        range_start=start,
        range_end=start + timedelta(hours=3),
    )
    assert gaps == []


def test_find_gaps_detects_single_missing_slot() -> None:
    start = datetime(2024, 1, 1, tzinfo=UTC)
    timestamps = [start, start + timedelta(hours=2), start + timedelta(hours=3)]
    gaps = find_gaps(
        timestamps,
        expected_interval=timedelta(hours=1),
        range_start=start,
        range_end=start + timedelta(hours=3),
    )
    assert gaps == [DataGap(start + timedelta(hours=1), start + timedelta(hours=1))]


def test_find_gaps_detects_multiple_disjoint_gaps() -> None:
    start = datetime(2024, 1, 1, tzinfo=UTC)
    # present: 0, 3, 4, 7  (missing 1,2 and 5,6)
    timestamps = [start + timedelta(hours=h) for h in (0, 3, 4, 7)]
    gaps = find_gaps(
        timestamps,
        expected_interval=timedelta(hours=1),
        range_start=start,
        range_end=start + timedelta(hours=7),
    )
    assert gaps == [
        DataGap(start + timedelta(hours=1), start + timedelta(hours=2)),
        DataGap(start + timedelta(hours=5), start + timedelta(hours=6)),
    ]


def test_find_gaps_rejects_invalid_range() -> None:
    start = datetime(2024, 1, 1, tzinfo=UTC)
    with pytest.raises(ValueError):
        find_gaps([], expected_interval=timedelta(hours=1), range_start=start, range_end=start - timedelta(hours=1))


def test_find_gaps_rejects_nonpositive_interval() -> None:
    start = datetime(2024, 1, 1, tzinfo=UTC)
    with pytest.raises(ValueError):
        find_gaps([], expected_interval=timedelta(0), range_start=start, range_end=start)


# --- HistoricalDataService --------------------------------------------------


class FakeProvider:
    """Records every call made to it and returns pre-programmed candles."""

    def __init__(self) -> None:
        self.ohlcv_calls: list[tuple[datetime, datetime]] = []
        self.funding_rate_calls: list[tuple[datetime, datetime]] = []
        self.open_interest_calls: list[tuple[datetime, datetime]] = []
        self.liquidation_calls: list[tuple[datetime, datetime]] = []
        self.long_short_ratio_calls: list[tuple[datetime, datetime]] = []
        self._candles_by_hour: dict[int, Candle] = {}
        self._funding_rates_by_hour: dict[int, FundingRate] = {}
        self._open_interest_by_hour: dict[int, OpenInterest] = {}
        self._liquidations_by_hour: dict[int, Liquidation] = {}
        self._long_short_ratios_by_hour: dict[int, LongShortRatio] = {}

    def seed_candle(self, hour: int) -> None:
        self._candles_by_hour[hour] = Candle(
            exchange="binance",
            symbol="btcusdt",
            timeframe=Timeframe.HOUR_1,
            timestamp=datetime(2024, 1, 1, hour, tzinfo=UTC),
            open=100,
            high=105,
            low=95,
            close=100,
            volume=1,
        )

    def seed_funding_rate(self, hour: int) -> None:
        self._funding_rates_by_hour[hour] = FundingRate(
            exchange="binance",
            symbol="btcusdt",
            timestamp=datetime(2024, 1, 1, hour, tzinfo=UTC),
            funding_rate=0.0001,
        )

    def seed_open_interest(self, hour: int) -> None:
        self._open_interest_by_hour[hour] = OpenInterest(
            exchange="binance",
            symbol="btcusdt",
            timestamp=datetime(2024, 1, 1, hour, tzinfo=UTC),
            open_interest=1000,
        )

    def seed_liquidation(self, hour: int) -> None:
        self._liquidations_by_hour[hour] = Liquidation(
            exchange="binance",
            symbol="btcusdt",
            timestamp=datetime(2024, 1, 1, hour, tzinfo=UTC),
            long_liquidation_usd=100,
            short_liquidation_usd=50,
        )

    def seed_long_short_ratio(self, hour: int) -> None:
        self._long_short_ratios_by_hour[hour] = LongShortRatio(
            exchange="binance",
            symbol="btcusdt",
            timestamp=datetime(2024, 1, 1, hour, tzinfo=UTC),
            long_account_ratio=0.5,
            short_account_ratio=0.5,
        )

    def get_ohlcv(self, *, exchange: str, symbol: str, timeframe: Timeframe, start: datetime, end: datetime) -> list[Candle]:
        self.ohlcv_calls.append((start, end))
        return [
            candle
            for hour, candle in sorted(self._candles_by_hour.items())
            if start <= candle.timestamp <= end
        ]

    def get_funding_rate(
        self, *, exchange: str, symbol: str, timeframe: Timeframe, start: datetime, end: datetime
    ) -> list[FundingRate]:
        self.funding_rate_calls.append((start, end))
        return [
            rate
            for hour, rate in sorted(self._funding_rates_by_hour.items())
            if start <= rate.timestamp <= end
        ]

    def get_open_interest(
        self, *, exchange: str, symbol: str, timeframe: Timeframe, start: datetime, end: datetime
    ) -> list[OpenInterest]:
        self.open_interest_calls.append((start, end))
        return [
            record
            for hour, record in sorted(self._open_interest_by_hour.items())
            if start <= record.timestamp <= end
        ]

    def get_liquidations(
        self, *, exchange: str, symbol: str, timeframe: Timeframe, start: datetime, end: datetime
    ) -> list[Liquidation]:
        self.liquidation_calls.append((start, end))
        return [
            record
            for hour, record in sorted(self._liquidations_by_hour.items())
            if start <= record.timestamp <= end
        ]

    def get_long_short_ratio(
        self, *, exchange: str, symbol: str, timeframe: Timeframe, start: datetime, end: datetime
    ) -> list[LongShortRatio]:
        self.long_short_ratio_calls.append((start, end))
        return [
            record
            for hour, record in sorted(self._long_short_ratios_by_hour.items())
            if start <= record.timestamp <= end
        ]


@pytest.fixture
def repository(tmp_path: Path) -> DataRepository:
    return DataRepository(tmp_path)


def test_ensure_ohlcv_fetches_whole_range_on_empty_cache(repository: DataRepository) -> None:
    provider = FakeProvider()
    for hour in range(4):
        provider.seed_candle(hour)
    service = HistoricalDataService(provider, repository)

    start, end = datetime(2024, 1, 1, 0, tzinfo=UTC), datetime(2024, 1, 1, 3, tzinfo=UTC)
    result = service.ensure_ohlcv(exchange="binance", symbol="btcusdt", timeframe=Timeframe.HOUR_1, start=start, end=end)

    assert len(result) == 4
    assert provider.ohlcv_calls == [(start, end)]


def test_ensure_ohlcv_only_fetches_missing_sub_range(repository: DataRepository) -> None:
    provider = FakeProvider()
    for hour in range(6):
        provider.seed_candle(hour)
    service = HistoricalDataService(provider, repository)

    full_start, full_end = datetime(2024, 1, 1, 0, tzinfo=UTC), datetime(2024, 1, 1, 5, tzinfo=UTC)

    # Pre-populate everything except hours 2-3 directly into the repository,
    # bypassing the provider, to simulate a partially-cached range.
    for hour in (0, 1, 4, 5):
        repository.write(
            Candle,
            [provider._candles_by_hour[hour]],
            exchange="binance",
            symbol="btcusdt",
            timeframe=Timeframe.HOUR_1,
        )

    result = service.ensure_ohlcv(
        exchange="binance", symbol="btcusdt", timeframe=Timeframe.HOUR_1, start=full_start, end=full_end
    )

    assert len(result) == 6
    assert provider.ohlcv_calls == [
        (datetime(2024, 1, 1, 2, tzinfo=UTC), datetime(2024, 1, 1, 3, tzinfo=UTC))
    ]


def test_ensure_ohlcv_does_not_call_provider_when_fully_cached(repository: DataRepository) -> None:
    provider = FakeProvider()
    for hour in range(3):
        provider.seed_candle(hour)
        repository.write(
            Candle,
            [provider._candles_by_hour[hour]],
            exchange="binance",
            symbol="btcusdt",
            timeframe=Timeframe.HOUR_1,
        )

    service = HistoricalDataService(provider, repository)
    result = service.ensure_ohlcv(
        exchange="binance",
        symbol="btcusdt",
        timeframe=Timeframe.HOUR_1,
        start=datetime(2024, 1, 1, 0, tzinfo=UTC),
        end=datetime(2024, 1, 1, 2, tzinfo=UTC),
    )
    assert len(result) == 3
    assert provider.ohlcv_calls == []


def test_ensure_ohlcv_handles_provider_returning_nothing_for_gap(repository: DataRepository) -> None:
    provider = FakeProvider()  # no candles seeded anywhere
    service = HistoricalDataService(provider, repository)

    result = service.ensure_ohlcv(
        exchange="binance",
        symbol="btcusdt",
        timeframe=Timeframe.HOUR_1,
        start=datetime(2024, 1, 1, 0, tzinfo=UTC),
        end=datetime(2024, 1, 1, 1, tzinfo=UTC),
    )
    assert result == []
    assert len(provider.ohlcv_calls) == 1


def test_detect_gaps_does_not_touch_provider(repository: DataRepository) -> None:
    provider = FakeProvider()
    service = HistoricalDataService(provider, repository)
    gaps = service.detect_gaps(
        Candle,
        exchange="binance",
        symbol="btcusdt",
        timeframe=Timeframe.HOUR_1,
        start=datetime(2024, 1, 1, 0, tzinfo=UTC),
        end=datetime(2024, 1, 1, 2, tzinfo=UTC),
        expected_interval=Timeframe.HOUR_1.duration,
    )
    assert len(gaps) == 1
    assert provider.ohlcv_calls == []


def test_ensure_funding_rate_uses_timeframe_for_gap_detection(repository: DataRepository) -> None:
    provider = FakeProvider()
    for hour in (0, 8, 16):
        provider.seed_funding_rate(hour)
    service = HistoricalDataService(provider, repository)

    result = service.ensure_funding_rate(
        exchange="binance",
        symbol="btcusdt",
        timeframe=Timeframe.HOUR_8,
        start=datetime(2024, 1, 1, 0, tzinfo=UTC),
        end=datetime(2024, 1, 1, 16, tzinfo=UTC),
    )
    assert len(result) == 3
    assert provider.funding_rate_calls == [
        (datetime(2024, 1, 1, 0, tzinfo=UTC), datetime(2024, 1, 1, 16, tzinfo=UTC))
    ]


def test_ensure_open_interest_uses_timeframe_for_gap_detection(repository: DataRepository) -> None:
    provider = FakeProvider()
    for hour in range(3):
        provider.seed_open_interest(hour)
    service = HistoricalDataService(provider, repository)

    result = service.ensure_open_interest(
        exchange="binance",
        symbol="btcusdt",
        timeframe=Timeframe.HOUR_1,
        start=datetime(2024, 1, 1, 0, tzinfo=UTC),
        end=datetime(2024, 1, 1, 2, tzinfo=UTC),
    )
    assert len(result) == 3
    assert provider.open_interest_calls == [
        (datetime(2024, 1, 1, 0, tzinfo=UTC), datetime(2024, 1, 1, 2, tzinfo=UTC))
    ]


def test_ensure_liquidations_uses_timeframe_for_gap_detection(repository: DataRepository) -> None:
    provider = FakeProvider()
    for hour in range(3):
        provider.seed_liquidation(hour)
    service = HistoricalDataService(provider, repository)

    result = service.ensure_liquidations(
        exchange="binance",
        symbol="btcusdt",
        timeframe=Timeframe.HOUR_1,
        start=datetime(2024, 1, 1, 0, tzinfo=UTC),
        end=datetime(2024, 1, 1, 2, tzinfo=UTC),
    )
    assert len(result) == 3
    assert provider.liquidation_calls == [
        (datetime(2024, 1, 1, 0, tzinfo=UTC), datetime(2024, 1, 1, 2, tzinfo=UTC))
    ]


def test_ensure_long_short_ratio_uses_timeframe_for_gap_detection(repository: DataRepository) -> None:
    provider = FakeProvider()
    for hour in range(3):
        provider.seed_long_short_ratio(hour)
    service = HistoricalDataService(provider, repository)

    result = service.ensure_long_short_ratio(
        exchange="binance",
        symbol="btcusdt",
        timeframe=Timeframe.HOUR_1,
        start=datetime(2024, 1, 1, 0, tzinfo=UTC),
        end=datetime(2024, 1, 1, 2, tzinfo=UTC),
    )
    assert len(result) == 3
    assert provider.long_short_ratio_calls == [
        (datetime(2024, 1, 1, 0, tzinfo=UTC), datetime(2024, 1, 1, 2, tzinfo=UTC))
    ]


def test_different_timeframes_are_cached_separately(repository: DataRepository) -> None:
    """Requesting 1h and 8h funding rate for the same symbol must not collide
    in the cache — they are different series, not interchangeable."""
    provider = FakeProvider()
    provider.seed_funding_rate(0)
    service = HistoricalDataService(provider, repository)

    service.ensure_funding_rate(
        exchange="binance", symbol="btcusdt", timeframe=Timeframe.HOUR_1,
        start=datetime(2024, 1, 1, 0, tzinfo=UTC), end=datetime(2024, 1, 1, 0, tzinfo=UTC),
    )
    assert len(provider.funding_rate_calls) == 1

    # Same range, different timeframe -> must be treated as an empty cache
    # for THAT timeframe and re-fetched, not served from the 1h cache file.
    service.ensure_funding_rate(
        exchange="binance", symbol="btcusdt", timeframe=Timeframe.HOUR_8,
        start=datetime(2024, 1, 1, 0, tzinfo=UTC), end=datetime(2024, 1, 1, 0, tzinfo=UTC),
    )
    assert len(provider.funding_rate_calls) == 2
