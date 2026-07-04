"""Local historical-data cache backed by Parquet files, queried via DuckDB.

One Parquet file per (record type, exchange, symbol[, timeframe]) partition
under the configured cache root. Writes merge new records into any existing
file, deduplicating by timestamp, so repeated syncs from the provider are
idempotent. Reads push the timestamp-range filter down to DuckDB instead of
loading an entire file into memory.

This module has no knowledge of CoinGlass or any other provider — it only
deals in the canonical schema types.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence, TypeVar

import duckdb
import pandas as pd

from btengine.data.errors import CacheError
from btengine.data.schema import (
    Candle,
    CanonicalRecord,
    FundingRate,
    Liquidation,
    LongShortRatio,
    OpenInterest,
    Timeframe,
)

RecordT = TypeVar("RecordT", bound=CanonicalRecord)

_RECORD_SUBDIR: dict[type[CanonicalRecord], str] = {
    Candle: "candles",
    FundingRate: "funding_rate",
    OpenInterest: "open_interest",
    Liquidation: "liquidation",
    LongShortRatio: "long_short_ratio",
}


def _to_py_datetime(value: object) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    to_pydatetime = getattr(value, "to_pydatetime", None)
    if callable(to_pydatetime):
        return _to_py_datetime(to_pydatetime())
    raise CacheError(f"Could not interpret cached value as a timestamp: {value!r}")


class DataRepository:
    """Parquet+DuckDB backed cache for canonical market data records."""

    def __init__(self, root: Path | str) -> None:
        self._root = Path(root)

    def _path_for(
        self,
        model_cls: type[CanonicalRecord],
        *,
        exchange: str,
        symbol: str,
        timeframe: Timeframe | None = None,
    ) -> Path:
        subdir = _RECORD_SUBDIR[model_cls]
        directory = self._root / subdir / exchange.upper() / symbol.upper()
        filename = f"{timeframe.value}.parquet" if timeframe is not None else "data.parquet"
        return directory / filename

    def write(
        self,
        model_cls: type[RecordT],
        records: Sequence[RecordT],
        *,
        exchange: str,
        symbol: str,
        timeframe: Timeframe | None = None,
    ) -> None:
        """Merge ``records`` into the cache file, deduplicating by timestamp."""
        if not records:
            return
        path = self._path_for(model_cls, exchange=exchange, symbol=symbol, timeframe=timeframe)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            rows = []
            for record in records:
                row = record.model_dump()
                row.pop("timeframe", None)  # implied by the file path, not stored
                rows.append(row)
            new_df = pd.DataFrame(rows)
            new_df["timestamp"] = pd.to_datetime(new_df["timestamp"], utc=True)

            if path.exists():
                existing_df = pd.read_parquet(path)
                combined = pd.concat([existing_df, new_df], ignore_index=True)
            else:
                combined = new_df

            combined = combined.drop_duplicates(subset=["timestamp"], keep="last")
            combined = combined.sort_values("timestamp").reset_index(drop=True)
            combined.to_parquet(path, index=False)
        except Exception as exc:  # noqa: BLE001 - boundary layer: never let a raw I/O crash escape
            raise CacheError(
                f"Failed writing cache file {path}", context={"path": str(path)}
            ) from exc

    def read(
        self,
        model_cls: type[RecordT],
        *,
        exchange: str,
        symbol: str,
        timeframe: Timeframe | None = None,
        start: datetime,
        end: datetime,
    ) -> list[RecordT]:
        """Return cached records in ``[start, end]``, or ``[]`` if nothing is cached."""
        path = self._path_for(model_cls, exchange=exchange, symbol=symbol, timeframe=timeframe)
        if not path.exists():
            return []
        try:
            connection = duckdb.connect()
            try:
                frame = connection.execute(
                    "SELECT * FROM read_parquet(?) WHERE timestamp >= ? AND timestamp <= ? "
                    "ORDER BY timestamp",
                    [str(path), start, end],
                ).df()
            finally:
                connection.close()
        except Exception as exc:  # noqa: BLE001
            raise CacheError(
                f"Failed reading cache file {path}", context={"path": str(path)}
            ) from exc

        records: list[RecordT] = []
        for row in frame.to_dict(orient="records"):
            kwargs = dict(row)
            kwargs["timestamp"] = _to_py_datetime(kwargs["timestamp"])
            # `timeframe` only determines the cache file path (see
            # _path_for); it is only also a *model field* for Candle, so it
            # must not be re-injected into record types that don't have it
            # (FundingRate, OpenInterest, Liquidation, LongShortRatio).
            if timeframe is not None and "timeframe" in model_cls.model_fields:
                kwargs["timeframe"] = timeframe
            records.append(model_cls(**kwargs))
        return records

    def covered_range(
        self,
        model_cls: type[CanonicalRecord],
        *,
        exchange: str,
        symbol: str,
        timeframe: Timeframe | None = None,
    ) -> tuple[datetime, datetime] | None:
        """Return the (min, max) cached timestamp for this partition, or ``None`` if empty."""
        path = self._path_for(model_cls, exchange=exchange, symbol=symbol, timeframe=timeframe)
        if not path.exists():
            return None
        try:
            connection = duckdb.connect()
            try:
                row = connection.execute(
                    "SELECT MIN(timestamp), MAX(timestamp) FROM read_parquet(?)", [str(path)]
                ).fetchone()
            finally:
                connection.close()
        except Exception as exc:  # noqa: BLE001
            raise CacheError(
                f"Failed reading cache file {path}", context={"path": str(path)}
            ) from exc
        if row is None or row[0] is None:
            return None
        return (_to_py_datetime(row[0]), _to_py_datetime(row[1]))
