from datetime import datetime, timezone
from pathlib import Path

import pytest

from btengine.feature_store.errors import FeatureStoreError
from btengine.feature_store.local_store import LocalFeatureStore
from btengine.features.base import FeatureValue

UTC = timezone.utc


def _value(
    hour: int, value: float = 1.0, symbol: str = "BTCUSDT", feature_name: str = "atr_14", version: str = "v1"
) -> FeatureValue:
    return FeatureValue(
        symbol=symbol, feature_name=feature_name, timestamp=datetime(2024, 1, 1, hour, tzinfo=UTC),
        value=value, version=version,
    )


def test_read_returns_empty_when_nothing_stored(tmp_path: Path) -> None:
    store = LocalFeatureStore(tmp_path)
    result = store.read(
        symbol="BTCUSDT", feature_name="atr_14",
        start=datetime(2024, 1, 1, tzinfo=UTC), end=datetime(2024, 1, 2, tzinfo=UTC),
    )
    assert result == []


def test_write_then_read_roundtrip(tmp_path: Path) -> None:
    store = LocalFeatureStore(tmp_path)
    values = [_value(0, 1.0), _value(1, 2.0), _value(2, 3.0)]
    store.write(values)

    result = store.read(
        symbol="BTCUSDT", feature_name="atr_14",
        start=datetime(2024, 1, 1, 0, tzinfo=UTC), end=datetime(2024, 1, 1, 2, tzinfo=UTC),
    )
    assert len(result) == 3
    assert [v.value for v in result] == [1.0, 2.0, 3.0]
    assert all(v.feature_name == "atr_14" for v in result)
    assert all(v.symbol == "BTCUSDT" for v in result)


def test_write_deduplicates_by_timestamp_keeping_latest(tmp_path: Path) -> None:
    store = LocalFeatureStore(tmp_path)
    store.write([_value(0, value=1.0)])
    store.write([_value(0, value=99.0)])

    result = store.read(
        symbol="BTCUSDT", feature_name="atr_14",
        start=datetime(2024, 1, 1, tzinfo=UTC), end=datetime(2024, 1, 2, tzinfo=UTC),
    )
    assert len(result) == 1
    assert result[0].value == 99.0


def test_different_feature_names_are_stored_separately(tmp_path: Path) -> None:
    store = LocalFeatureStore(tmp_path)
    store.write([_value(0, value=1.0, feature_name="atr_14")])
    store.write([_value(0, value=2.0, feature_name="cvd")])

    atr = store.read(symbol="BTCUSDT", feature_name="atr_14", start=datetime(2024, 1, 1, tzinfo=UTC), end=datetime(2024, 1, 2, tzinfo=UTC))
    cvd = store.read(symbol="BTCUSDT", feature_name="cvd", start=datetime(2024, 1, 1, tzinfo=UTC), end=datetime(2024, 1, 2, tzinfo=UTC))
    assert atr[0].value == 1.0
    assert cvd[0].value == 2.0


def test_different_symbols_are_stored_separately(tmp_path: Path) -> None:
    store = LocalFeatureStore(tmp_path)
    store.write([_value(0, value=1.0, symbol="BTCUSDT")])
    store.write([_value(0, value=2.0, symbol="ETHUSDT")])

    btc = store.read(symbol="BTCUSDT", feature_name="atr_14", start=datetime(2024, 1, 1, tzinfo=UTC), end=datetime(2024, 1, 2, tzinfo=UTC))
    eth = store.read(symbol="ETHUSDT", feature_name="atr_14", start=datetime(2024, 1, 1, tzinfo=UTC), end=datetime(2024, 1, 2, tzinfo=UTC))
    assert btc[0].value == 1.0
    assert eth[0].value == 2.0


def test_write_with_empty_sequence_is_a_noop(tmp_path: Path) -> None:
    store = LocalFeatureStore(tmp_path)
    store.write([])
    result = store.read(symbol="BTCUSDT", feature_name="atr_14", start=datetime(2024, 1, 1, tzinfo=UTC), end=datetime(2024, 1, 2, tzinfo=UTC))
    assert result == []


def test_write_handles_mixed_symbols_and_features_in_one_call(tmp_path: Path) -> None:
    store = LocalFeatureStore(tmp_path)
    store.write([
        _value(0, value=1.0, symbol="BTCUSDT", feature_name="atr_14"),
        _value(0, value=2.0, symbol="ETHUSDT", feature_name="cvd"),
    ])
    btc = store.read(symbol="BTCUSDT", feature_name="atr_14", start=datetime(2024, 1, 1, tzinfo=UTC), end=datetime(2024, 1, 2, tzinfo=UTC))
    eth = store.read(symbol="ETHUSDT", feature_name="cvd", start=datetime(2024, 1, 1, tzinfo=UTC), end=datetime(2024, 1, 2, tzinfo=UTC))
    assert btc[0].value == 1.0
    assert eth[0].value == 2.0


def test_read_filters_by_range(tmp_path: Path) -> None:
    store = LocalFeatureStore(tmp_path)
    store.write([_value(h) for h in range(5)])
    result = store.read(
        symbol="BTCUSDT", feature_name="atr_14",
        start=datetime(2024, 1, 1, 1, tzinfo=UTC), end=datetime(2024, 1, 1, 3, tzinfo=UTC),
    )
    assert [v.timestamp.hour for v in result] == [1, 2, 3]


def test_read_raises_feature_store_error_on_corrupt_file(tmp_path: Path) -> None:
    store = LocalFeatureStore(tmp_path)
    path = tmp_path / "BTCUSDT" / "atr_14.parquet"
    path.parent.mkdir(parents=True)
    path.write_text("not a parquet file")
    with pytest.raises(FeatureStoreError):
        store.read(symbol="BTCUSDT", feature_name="atr_14", start=datetime(2024, 1, 1, tzinfo=UTC), end=datetime(2024, 1, 2, tzinfo=UTC))


def test_write_raises_feature_store_error_when_path_cannot_be_created(tmp_path: Path) -> None:
    store = LocalFeatureStore(tmp_path)
    blocking_file = tmp_path / "BTCUSDT"
    blocking_file.parent.mkdir(parents=True, exist_ok=True)
    blocking_file.write_text("blocking")
    with pytest.raises(FeatureStoreError):
        store.write([_value(0)])


# --- versioning ---------------------------------------------------------


def test_values_default_to_version_v1() -> None:
    assert _value(0).version == "v1"


def test_different_versions_of_the_same_timestamp_coexist(tmp_path: Path) -> None:
    store = LocalFeatureStore(tmp_path)
    store.write([_value(0, value=1.0, version="v1")])
    store.write([_value(0, value=2.0, version="v2")])

    result = store.read(
        symbol="BTCUSDT", feature_name="atr_14",
        start=datetime(2024, 1, 1, tzinfo=UTC), end=datetime(2024, 1, 2, tzinfo=UTC),
    )
    assert len(result) == 2
    by_version = {v.version: v.value for v in result}
    assert by_version == {"v1": 1.0, "v2": 2.0}


def test_rewriting_the_same_version_and_timestamp_overwrites_only_that_version(tmp_path: Path) -> None:
    store = LocalFeatureStore(tmp_path)
    store.write([_value(0, value=1.0, version="v1")])
    store.write([_value(0, value=2.0, version="v2")])
    store.write([_value(0, value=99.0, version="v1")])  # re-compute v1 only

    result = store.read(
        symbol="BTCUSDT", feature_name="atr_14",
        start=datetime(2024, 1, 1, tzinfo=UTC), end=datetime(2024, 1, 2, tzinfo=UTC),
    )
    by_version = {v.version: v.value for v in result}
    assert by_version == {"v1": 99.0, "v2": 2.0}


def test_read_can_filter_to_a_single_version(tmp_path: Path) -> None:
    store = LocalFeatureStore(tmp_path)
    store.write([_value(0, value=1.0, version="v1")])
    store.write([_value(0, value=2.0, version="v2")])

    v1_only = store.read(
        symbol="BTCUSDT", feature_name="atr_14",
        start=datetime(2024, 1, 1, tzinfo=UTC), end=datetime(2024, 1, 2, tzinfo=UTC),
        version="v1",
    )
    assert len(v1_only) == 1
    assert v1_only[0].value == 1.0
    assert v1_only[0].version == "v1"


def test_writing_over_a_legacy_file_without_a_version_column_backfills_v1(tmp_path: Path) -> None:
    import pandas as pd

    store = LocalFeatureStore(tmp_path)
    path = tmp_path / "BTCUSDT" / "atr_14.parquet"
    path.parent.mkdir(parents=True)
    legacy_df = pd.DataFrame(
        {"timestamp": [datetime(2024, 1, 1, 0, tzinfo=UTC)], "value": [1.0]}  # no "version" column
    )
    legacy_df.to_parquet(path, index=False)

    store.write([_value(1, value=2.0, version="v1")])

    result = store.read(
        symbol="BTCUSDT", feature_name="atr_14",
        start=datetime(2024, 1, 1, tzinfo=UTC), end=datetime(2024, 1, 2, tzinfo=UTC),
    )
    by_hour = {v.timestamp.hour: (v.value, v.version) for v in result}
    assert by_hour[0] == (1.0, "v1")
    assert by_hour[1] == (2.0, "v1")


def test_read_returns_all_versions_when_version_not_specified(tmp_path: Path) -> None:
    store = LocalFeatureStore(tmp_path)
    store.write([_value(0, value=1.0, version="v1")])
    store.write([_value(0, value=2.0, version="v2")])

    result = store.read(
        symbol="BTCUSDT", feature_name="atr_14",
        start=datetime(2024, 1, 1, tzinfo=UTC), end=datetime(2024, 1, 2, tzinfo=UTC),
    )
    assert len(result) == 2
