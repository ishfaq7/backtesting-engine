from datetime import datetime, timezone
from pathlib import Path

import pytest

from btengine.data.errors import CacheError
from btengine.data.repository import DataRepository, _to_py_datetime
from btengine.data.schema import Candle, FundingRate, Timeframe

UTC = timezone.utc


def _candle(hour: int, close: float = 100.0) -> Candle:
    return Candle(
        exchange="binance",
        symbol="btcusdt",
        timeframe=Timeframe.HOUR_1,
        timestamp=datetime(2024, 1, 1, hour, tzinfo=UTC),
        open=close,
        high=close + 5,
        low=close - 5,
        close=close,
        volume=1,
    )


def test_read_returns_empty_list_when_nothing_cached(tmp_path: Path) -> None:
    repo = DataRepository(tmp_path)
    result = repo.read(
        Candle,
        exchange="binance",
        symbol="btcusdt",
        timeframe=Timeframe.HOUR_1,
        start=datetime(2024, 1, 1, tzinfo=UTC),
        end=datetime(2024, 1, 2, tzinfo=UTC),
    )
    assert result == []


def test_covered_range_is_none_when_empty(tmp_path: Path) -> None:
    repo = DataRepository(tmp_path)
    assert (
        repo.covered_range(Candle, exchange="binance", symbol="btcusdt", timeframe=Timeframe.HOUR_1)
        is None
    )


def test_write_then_read_roundtrip(tmp_path: Path) -> None:
    repo = DataRepository(tmp_path)
    candles = [_candle(0), _candle(1), _candle(2)]
    repo.write(Candle, candles, exchange="binance", symbol="btcusdt", timeframe=Timeframe.HOUR_1)

    result = repo.read(
        Candle,
        exchange="binance",
        symbol="btcusdt",
        timeframe=Timeframe.HOUR_1,
        start=datetime(2024, 1, 1, 0, tzinfo=UTC),
        end=datetime(2024, 1, 1, 2, tzinfo=UTC),
    )

    assert len(result) == 3
    assert [c.timestamp.hour for c in result] == [0, 1, 2]
    assert all(isinstance(c, Candle) for c in result)
    assert all(c.timeframe == Timeframe.HOUR_1 for c in result)


def test_read_filters_by_range(tmp_path: Path) -> None:
    repo = DataRepository(tmp_path)
    candles = [_candle(h) for h in range(5)]
    repo.write(Candle, candles, exchange="binance", symbol="btcusdt", timeframe=Timeframe.HOUR_1)

    result = repo.read(
        Candle,
        exchange="binance",
        symbol="btcusdt",
        timeframe=Timeframe.HOUR_1,
        start=datetime(2024, 1, 1, 1, tzinfo=UTC),
        end=datetime(2024, 1, 1, 3, tzinfo=UTC),
    )
    assert [c.timestamp.hour for c in result] == [1, 2, 3]


def test_write_deduplicates_by_timestamp_keeping_latest(tmp_path: Path) -> None:
    repo = DataRepository(tmp_path)
    repo.write(Candle, [_candle(0, close=100)], exchange="binance", symbol="btcusdt", timeframe=Timeframe.HOUR_1)
    repo.write(Candle, [_candle(0, close=200)], exchange="binance", symbol="btcusdt", timeframe=Timeframe.HOUR_1)

    result = repo.read(
        Candle,
        exchange="binance",
        symbol="btcusdt",
        timeframe=Timeframe.HOUR_1,
        start=datetime(2024, 1, 1, tzinfo=UTC),
        end=datetime(2024, 1, 2, tzinfo=UTC),
    )
    assert len(result) == 1
    assert result[0].close == 200


def test_covered_range_reflects_min_and_max(tmp_path: Path) -> None:
    repo = DataRepository(tmp_path)
    repo.write(
        Candle, [_candle(0), _candle(3)], exchange="binance", symbol="btcusdt", timeframe=Timeframe.HOUR_1
    )
    start, end = repo.covered_range(
        Candle, exchange="binance", symbol="btcusdt", timeframe=Timeframe.HOUR_1
    )
    assert start == datetime(2024, 1, 1, 0, tzinfo=UTC)
    assert end == datetime(2024, 1, 1, 3, tzinfo=UTC)


def test_record_type_without_timeframe_uses_flat_filename(tmp_path: Path) -> None:
    repo = DataRepository(tmp_path)
    funding_rate = FundingRate(
        exchange="binance", symbol="btcusdt", timestamp=datetime(2024, 1, 1, tzinfo=UTC), funding_rate=0.0001
    )
    repo.write(FundingRate, [funding_rate], exchange="binance", symbol="btcusdt")

    expected_path = tmp_path / "funding_rate" / "BINANCE" / "BTCUSDT" / "data.parquet"
    assert expected_path.exists()

    result = repo.read(
        FundingRate,
        exchange="binance",
        symbol="btcusdt",
        start=datetime(2024, 1, 1, tzinfo=UTC),
        end=datetime(2024, 1, 2, tzinfo=UTC),
    )
    assert len(result) == 1
    assert result[0].funding_rate == 0.0001


def test_write_with_empty_records_is_a_noop(tmp_path: Path) -> None:
    repo = DataRepository(tmp_path)
    repo.write(Candle, [], exchange="binance", symbol="btcusdt", timeframe=Timeframe.HOUR_1)
    assert repo.covered_range(Candle, exchange="binance", symbol="btcusdt", timeframe=Timeframe.HOUR_1) is None


def test_read_raises_cache_error_on_corrupt_file(tmp_path: Path) -> None:
    repo = DataRepository(tmp_path)
    path = tmp_path / "candles" / "BINANCE" / "BTCUSDT" / "1h.parquet"
    path.parent.mkdir(parents=True)
    path.write_text("not a parquet file")

    with pytest.raises(CacheError):
        repo.read(
            Candle,
            exchange="binance",
            symbol="btcusdt",
            timeframe=Timeframe.HOUR_1,
            start=datetime(2024, 1, 1, tzinfo=UTC),
            end=datetime(2024, 1, 2, tzinfo=UTC),
        )


def test_covered_range_raises_cache_error_on_corrupt_file(tmp_path: Path) -> None:
    repo = DataRepository(tmp_path)
    path = tmp_path / "candles" / "BINANCE" / "BTCUSDT" / "1h.parquet"
    path.parent.mkdir(parents=True)
    path.write_text("not a parquet file")

    with pytest.raises(CacheError):
        repo.covered_range(Candle, exchange="binance", symbol="btcusdt", timeframe=Timeframe.HOUR_1)


def test_write_raises_cache_error_when_path_cannot_be_created(tmp_path: Path) -> None:
    repo = DataRepository(tmp_path)
    # Create a plain file where the repository needs a directory, forcing
    # mkdir() to fail with a structured CacheError instead of a raw OSError.
    blocking_file = tmp_path / "candles" / "BINANCE"
    blocking_file.parent.mkdir(parents=True)
    blocking_file.write_text("blocking")

    with pytest.raises(CacheError):
        repo.write(Candle, [_candle(0)], exchange="binance", symbol="btcusdt", timeframe=Timeframe.HOUR_1)


def test_to_py_datetime_rejects_unrecognized_values() -> None:
    with pytest.raises(CacheError):
        _to_py_datetime(object())


def test_covered_range_is_none_for_an_empty_parquet_file(tmp_path: Path) -> None:
    import pandas as pd

    repo = DataRepository(tmp_path)
    path = tmp_path / "candles" / "BINANCE" / "BTCUSDT" / "1h.parquet"
    path.parent.mkdir(parents=True)
    pd.DataFrame({"timestamp": pd.Series([], dtype="datetime64[ns, UTC]")}).to_parquet(path, index=False)

    assert repo.covered_range(Candle, exchange="binance", symbol="btcusdt", timeframe=Timeframe.HOUR_1) is None
