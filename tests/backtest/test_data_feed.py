from datetime import datetime, timezone
from pathlib import Path

import pytest

from btengine.backtest.data_feed import HistoricalCandleFeed
from btengine.data.repository import DataRepository
from btengine.data.schema import Candle, Timeframe

UTC = timezone.utc


def _candle(symbol: str, hour: int, price: float = 100.0) -> Candle:
    return Candle(
        exchange="binance",
        symbol=symbol,
        timeframe=Timeframe.HOUR_1,
        timestamp=datetime(2024, 1, 1, hour, tzinfo=UTC),
        open=price,
        high=price + 1,
        low=price - 1,
        close=price,
        volume=1,
    )


def test_rejects_empty_symbols(tmp_path: Path) -> None:
    repo = DataRepository(tmp_path)
    with pytest.raises(ValueError):
        HistoricalCandleFeed(
            repo, exchange="binance", symbols=[], timeframe=Timeframe.HOUR_1,
            start=datetime(2024, 1, 1, tzinfo=UTC), end=datetime(2024, 1, 2, tzinfo=UTC),
        )


def test_single_symbol_yields_in_chronological_order(tmp_path: Path) -> None:
    repo = DataRepository(tmp_path)
    candles = [_candle("BTCUSDT", h) for h in range(5)]
    repo.write(Candle, candles, exchange="binance", symbol="BTCUSDT", timeframe=Timeframe.HOUR_1)

    feed = HistoricalCandleFeed(
        repo, exchange="binance", symbols=["BTCUSDT"], timeframe=Timeframe.HOUR_1,
        start=datetime(2024, 1, 1, tzinfo=UTC), end=datetime(2024, 1, 1, 4, tzinfo=UTC),
    )
    result = list(feed.iter_chronological())
    assert [c.timestamp.hour for c in result] == [0, 1, 2, 3, 4]


def test_multiple_symbols_are_merged_chronologically(tmp_path: Path) -> None:
    repo = DataRepository(tmp_path)
    repo.write(Candle, [_candle("BTCUSDT", 0), _candle("BTCUSDT", 2)], exchange="binance", symbol="BTCUSDT", timeframe=Timeframe.HOUR_1)
    repo.write(Candle, [_candle("ETHUSDT", 1), _candle("ETHUSDT", 3)], exchange="binance", symbol="ETHUSDT", timeframe=Timeframe.HOUR_1)

    feed = HistoricalCandleFeed(
        repo, exchange="binance", symbols=["BTCUSDT", "ETHUSDT"], timeframe=Timeframe.HOUR_1,
        start=datetime(2024, 1, 1, tzinfo=UTC), end=datetime(2024, 1, 1, 3, tzinfo=UTC),
    )
    result = list(feed.iter_chronological())
    ordering = [(c.symbol, c.timestamp.hour) for c in result]
    assert ordering == [("BTCUSDT", 0), ("ETHUSDT", 1), ("BTCUSDT", 2), ("ETHUSDT", 3)]
    # timestamps must be non-decreasing across the whole merged stream
    timestamps = [c.timestamp for c in result]
    assert timestamps == sorted(timestamps)


def test_symbol_with_no_cached_data_is_simply_skipped(tmp_path: Path) -> None:
    repo = DataRepository(tmp_path)
    repo.write(Candle, [_candle("BTCUSDT", 0)], exchange="binance", symbol="BTCUSDT", timeframe=Timeframe.HOUR_1)

    feed = HistoricalCandleFeed(
        repo, exchange="binance", symbols=["BTCUSDT", "ETHUSDT"], timeframe=Timeframe.HOUR_1,
        start=datetime(2024, 1, 1, tzinfo=UTC), end=datetime(2024, 1, 1, 1, tzinfo=UTC),
    )
    result = list(feed.iter_chronological())
    assert len(result) == 1
    assert result[0].symbol == "BTCUSDT"
