"""Parquet + DuckDB backed :class:`FeatureStore`.

Mirrors the proven pattern in ``btengine.data.repository.DataRepository``
(one file per partition, idempotent merge-on-write, DuckDB range reads) —
deliberately re-implemented here rather than reused, since the Feature
Store is a distinct component from the Data Layer's repository and this
architecture pass must not modify existing modules.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path

import duckdb
import pandas as pd

from btengine.feature_store.base import FeatureStore
from btengine.feature_store.errors import FeatureStoreError
from btengine.features.base import FeatureValue


class LocalFeatureStore(FeatureStore):
    """Local Parquet cache of computed feature values, one file per
    (symbol, feature_name)."""

    def __init__(self, root: Path | str) -> None:
        self._root = Path(root)

    def _path_for(self, symbol: str, feature_name: str) -> Path:
        return self._root / symbol.upper() / f"{feature_name}.parquet"

    def write(self, values: Sequence[FeatureValue]) -> None:
        if not values:
            return
        grouped: dict[tuple[str, str], list[FeatureValue]] = defaultdict(list)
        for value in values:
            grouped[(value.symbol.upper(), value.feature_name)].append(value)
        for (symbol, feature_name), group in grouped.items():
            self._write_one(symbol, feature_name, group)

    def _write_one(self, symbol: str, feature_name: str, values: list[FeatureValue]) -> None:
        path = self._path_for(symbol, feature_name)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            new_df = pd.DataFrame({
                "timestamp": [value.timestamp for value in values],
                "value": [value.value for value in values],
            })
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
            raise FeatureStoreError(f"Failed writing feature store file {path}") from exc

    def read(
        self, *, symbol: str, feature_name: str, start: datetime, end: datetime
    ) -> list[FeatureValue]:
        path = self._path_for(symbol, feature_name)
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
            raise FeatureStoreError(f"Failed reading feature store file {path}") from exc

        results: list[FeatureValue] = []
        for row in frame.to_dict(orient="records"):
            timestamp = row["timestamp"]
            to_pydatetime = getattr(timestamp, "to_pydatetime", None)
            if callable(to_pydatetime):
                timestamp = to_pydatetime()
            results.append(
                FeatureValue(
                    symbol=symbol.upper(), feature_name=feature_name, timestamp=timestamp, value=row["value"]
                )
            )
        return results
